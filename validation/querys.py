from rdflib import Graph

def verify_isolated_scenario(g: Graph, expected_scenario: str):
    """
    Evaluates the airport graph against 4 distinct collapse scenarios.
    Ensures that ONLY the expected scenario is triggered (Strict Isolation).
    expected_scenario options: "baseline", "associative", "physical", "aerial", "prediction"
    """
    
    # Define prefixes for all queries
    prefixes = """
    PREFIX ns1: <http://example.org/>
    PREFIX ns2: <http://example.org/otv2:>
    """
    
    # Dictionary containing the 4 separate ASK queries
    queries = {
        "prediction": prefixes + """
            ASK { ?airport ns1:collapsed.value true . }
        """,
        
        "aerial": prefixes + """
            ASK {
                {
                    SELECT ?flyingTime (COUNT(?plane) AS ?planeCount)
                    WHERE { ?plane ns1:flying.value ?flyingTime . } 
                    GROUP BY ?flyingTime
                }
                FILTER(?planeCount >= 5)
            }
        """,
        
        "physical": prefixes + """
            ASK {
                {
                    SELECT (COUNT(?gate) AS ?total)
                    WHERE {
                        ?airport ns2:hasChild ?terminal .
                        ?terminal ns2:hasChild ?gate .
                    }
                }
                {
                    SELECT (COUNT(?occGate) AS ?occupied)
                    WHERE {
                        ?airport ns2:hasChild ?terminal .
                        ?terminal ns2:hasChild ?occGate .
                        ?occGate ns1:occupied.value true .
                    }
                }
                FILTER(?total > 0 && ?total = ?occupied)
            }
        """,
        
        "associative": prefixes + """
            ASK {
                {
                    SELECT (COUNT(DISTINCT ?gate) AS ?assignedCount)
                    WHERE { ?plane ns2:assignedTo ?gate . }
                }
                FILTER(?assignedCount >= 8)
            }
        """
    }

    # Execute all queries and store results
    results = {}
    for scenario_name, query_str in queries.items():
        results[scenario_name] = bool(list(g.query(query_str))[0])
        
    # Print the Header
    print("======================================================")
    print(f" TEST EXECUTION: Expected -> {expected_scenario.upper()}")
    print("======================================================")
    
    # Table Header
    print(f"| {'SCENARIO':<12} | {'OBTAINED':<10} | {'EXPECTED':<10} | {'PASS?':<5} |")
    print("|--------------|------------|------------|-------|")
    
    all_tests_passed = True
    active_scenarios = []

    # Print Table Rows and check strict isolation
    for scenario_name, obtained_result in results.items():
        # Determine what the result SHOULD be for this specific row
        expected_result = True if scenario_name == expected_scenario else False
        
        # Check if row passes
        row_passed = (obtained_result == expected_result)
        if not row_passed:
            all_tests_passed = False
            
        if obtained_result:
            active_scenarios.append(scenario_name)
            
        # Formatting the row strings
        obtained_str = "TRUE" if obtained_result else "FALSE"
        expected_str = "TRUE" if expected_result else "FALSE"
        pass_str = "YES" if row_passed else "NO"
        
        print(f"| {scenario_name.capitalize():<12} | {obtained_str:<10} | {expected_str:<10} | {pass_str:<5} |")

    # Print Footer and Final Verdict
    print("------------------------------------------------------")
    if len(active_scenarios) == 0:
        detected_str = "None (Baseline)"
    else:
        detected_str = ", ".join(active_scenarios)
        
    print(f"Detected as active : {detected_str}")
    
    # Final Validation
    if all_tests_passed:
        print("VERDICT            : SUCCESS")
    else:
        print("VERDICT            : FAILED")
        
    print("======================================================\n")
    
    return all_tests_passed