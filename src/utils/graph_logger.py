from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
import json
import warnings


class GraphLogger:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            self.driver.verify_connectivity()
            self.available = True
        except (ServiceUnavailable, Exception) as e:
            self.available = False
            self.driver = None
            warnings.warn(f"Neo4j connection unavailable: {e}. Graph logging will be skipped.")

    def log_run(self, question, baseline, configured, plan=None, reflection=None, sim_examples=None):
        if not self.available or not self.driver:
            return  # Silently skip if Neo4j is not available
        
        try:
            with self.driver.session() as session:
                session.run("""
                MERGE (r:Run {question:$q})
                SET r.baseline=$b, r.configured=$c, r.plan=$p, r.reflection=$rfl
                """, q=question, b=baseline, c=configured, p=plan, rfl=json.dumps(reflection))

                if sim_examples:
                    for sim_result in sim_examples:
                        ex = sim_result["sample"]
                        sim = sim_result["similarity"]
                        session.run("""
                        MERGE (e:Example {category:$cat, question:$eq})
                        MERGE (r:Run {question:$q})
                        MERGE (r)-[:SIMILAR_TO {score:$sim}]->(e)
                        """, q=question, cat=ex.get("category"), eq=ex.get("question"), sim=sim)
        except Exception as e:
            warnings.warn(f"Failed to log to Neo4j: {e}")
    
    def close(self):
        if self.driver:
            self.driver.close()

