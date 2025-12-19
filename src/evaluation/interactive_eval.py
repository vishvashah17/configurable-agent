import time
import os
from utils.vector_index import DatasetVectorIndex
from utils.graph_logger import GraphLogger
from agent.baseline_agent import BaselineAgent
from agent.agent_controller import ConfigurableAgent
from evaluation.result_logger import ResultLogger
from evaluation.metrics import compute_bleu, compute_rouge


def interactive_run(question, expected=None, index=None, baseline=None, configured=None, logger=None, result_logger=None):
    start_time = time.time()
    
    # Query similar examples
    similar = index.query(question, top_k=3) if index else []

    # Auto-detect expected answer from similar examples if not provided
    auto_expected = None
    if not expected and similar and len(similar) > 0:
        top_match = similar[0]
        if top_match.get('similarity', 0) > 0.9:
            auto_expected = top_match['sample'].get('answer', None)
            if auto_expected:
                print(f"\n[Auto-detected expected answer from dataset (similarity: {top_match['similarity']:.3f})]")

    expected_to_use = expected or auto_expected

    # Run agents
    base_out = baseline.run(question) if baseline else "[Baseline not initialized]"
    conf = configured.run(question, expected_to_use) if configured else {"plan": "", "answer": "[Agent not initialized]", "reflection": {}}

    elapsed_time = time.time() - start_time

    # Compute metrics
    bleu = compute_bleu(conf["answer"], expected_to_use or base_out)
    rouge = compute_rouge(conf["answer"], expected_to_use or base_out)

    print("\n--- QUESTION ---")
    print(question)
    
    if "persona" in conf and conf["persona"]:
        print(f"\n[Persona: {conf['persona'].replace('_', ' ').title()}]")
    
    print("\nBaseline Output:\n", base_out)
    print("\nConfigurable Agent Output:")
    print("Plan:", conf["plan"])
    print("Answer:", conf["answer"])
    print("Reflection:", conf["reflection"])
    
    print("\nTop similar examples:")
    for s in similar:
        print(f"  {s['sample']['category']} (sim={s['similarity']:.3f}): {s['sample']['question'][:80]}")
        if s.get('similarity', 0) > 0.9 and s['sample'].get('answer'):
            print(f"    [Expected Answer: {s['sample']['answer'][:100]}...]")
    
    print(f"Time: {elapsed_time:.2f}s")

    # Try to log to Neo4j (optional)
    if logger:
        try:
            logger.log_run(question, base_out, conf["answer"], conf["plan"], conf["reflection"], similar)
        except Exception:
            pass

    # Save JSON result
    if result_logger:
        result_logger.save_result(
            question=question,
            baseline=base_out,
            configurable=conf,
            similar=similar,
            reflection=conf.get("reflection"),
            metrics={"bleu": bleu, "rouge": rouge, "execution_time": elapsed_time}
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Configurable Agent Interactive Evaluation")
    print("=" * 60)
    print("Initializing components (this may take a moment)...")
    
    try:
        print("Loading vector index...")
        index = DatasetVectorIndex(sample_n=200)
        
        print("Initializing baseline agent...")
        baseline = BaselineAgent()
        
        print("Initializing configurable agent...")
        if os.path.exists("src/config/base_config.yaml"):
            config_path = "src/config/base_config.yaml"
        else:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "base_config.yaml")
        configured = ConfigurableAgent(config_path)
        
        print("Connecting to Neo4j (optional)...")
        logger = GraphLogger()  # Safe to fail
        
        print("Initializing result logger...")
        result_logger = ResultLogger()

        print("\n" + "=" * 60)
        print("Ready! Enter questions to evaluate.")
        print("Type 'exit' or 'quit' to stop.")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        exit(1)
    
    try:
        while True:
            question = input("\nEnter your question (or 'exit' to quit): ").strip()
            if question.lower() in ['exit', 'quit', 'q']:
                print("\nExiting... Goodbye!")
                break
            if not question:
                continue
            
            expected = input("Enter expected answer (optional, press Enter to skip): ").strip() or None
            
            try:
                interactive_run(question, expected, index, baseline, configured, logger, result_logger)
            except Exception as e:
                print(f"\nError during evaluation: {e}")
                continue
                
    except KeyboardInterrupt:
        print("\n\nShutting down... Goodbye!")
    finally:
        if logger and logger.driver:
            logger.close()
