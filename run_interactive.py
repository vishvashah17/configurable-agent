"""
Wrapper script to run interactive evaluation from project root.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Change to src directory for proper imports
os.chdir(os.path.join(os.path.dirname(__file__), 'src'))

# Now run the interactive eval
if __name__ == "__main__":
    from evaluation.interactive_eval import interactive_run
    from utils.vector_index import DatasetVectorIndex
    from utils.graph_logger import GraphLogger
    from agent.baseline_agent import BaselineAgent
    from agent.agent_controller import ConfigurableAgent
    from evaluation.metrics import compute_bleu, compute_rouge
    
    print("=" * 60)
    print("Configurable Agent Interactive Evaluation")
    print("=" * 60)
    print("Initializing components (this may take a moment)...")
    
    # Initialize components once (reused for all questions)
    try:
        print("Loading vector index...")
        index = DatasetVectorIndex(sample_n=200)
        
        print("Initializing baseline agent...")
        baseline = BaselineAgent()
        
        print("Initializing configurable agent...")
        config_path = "config/base_config.yaml"
        configured = ConfigurableAgent(config_path)
        
        print("Connecting to Neo4j (optional)...")
        logger = GraphLogger()  # Will gracefully handle if unavailable
        
        print("\n" + "=" * 60)
        print("Ready! Enter questions to evaluate.")
        print("Type 'exit' or 'quit' to stop, or Ctrl+C to interrupt.")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        print("Exiting...")
        exit(1)
    
    try:
        while True:
            question = input("\nEnter your question (or 'exit' to quit): ").strip()
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("\nExiting... Goodbye!")
                break
            
            if not question:
                print("Please enter a valid question.")
                continue
            
            expected = input("Enter expected answer (optional, press Enter to skip): ").strip() or None
            
            try:
                interactive_run(question, expected, index, baseline, configured, logger)
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Exiting...")
                break
            except Exception as e:
                print(f"\nError during evaluation: {e}")
                print("Continuing to next question...")
                continue
                
    except KeyboardInterrupt:
        print("\n\nShutting down... Goodbye!")
    finally:
        # Cleanup
        if logger and logger.driver:
            logger.close()

