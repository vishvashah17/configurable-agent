"""Check current dataset counts and complete ProofWriter loading if needed."""
from load_datasets_to_neo4j import Neo4jLoader
import os

loader = Neo4jLoader("neo4j://127.0.0.1:7687", "neo4j", "password", "neo4j")

try:
    # Check current counts
    with loader.driver.session(database="neo4j") as session:
        result = session.run("""
            MATCH (n:Dataset) 
            RETURN labels(n)[0] as dataset, count(n) as count 
            ORDER BY dataset
        """)
        print("Current dataset counts in Neo4j:")
        print("=" * 50)
        for record in result:
            print(f"  {record['dataset']}: {record['count']} records")
        
        # Check if ProofWriter needs to be loaded
        result = session.run("MATCH (p:ProofWriter) RETURN count(p) as count")
        proofwriter_count = result.single()['count']
        print(f"\nProofWriter records: {proofwriter_count}")
        
        if proofwriter_count < 500000:  # Expected around 585k
            print("\nProofWriter dataset appears incomplete. Completing load...")
            proofwriter_path = os.path.join("datasets", "proofwriter.csv")
            if os.path.exists(proofwriter_path):
                loader.load_proofwriter(proofwriter_path)
            else:
                print(f"ProofWriter file not found at {proofwriter_path}")
        else:
            print("\nAll datasets appear to be loaded!")
            
        # Final summary
        print("\n" + "=" * 50)
        print("Final Summary:")
        print("=" * 50)
        result = session.run("""
            MATCH (n:Dataset) 
            RETURN labels(n)[0] as dataset, count(n) as count 
            ORDER BY dataset
        """)
        for record in result:
            print(f"  {record['dataset']}: {record['count']} records")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    loader.close()

