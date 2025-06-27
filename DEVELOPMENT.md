# Development

See the primary README for all development notes, at the moment.

# Abstraction notes

    FlexEval is a tool to run Evals.
    An Eval is a specification of transformations that should happen to 1+ data files and produce to a specific 
    - Approach 1: A Configuration tells the FlexEval tool how to execute an Eval.
    - Approach 2: An Eval knows how FlexEval should execute it, because it contains a Configuration.
    - Approach 3: An Eval is a specific metric computation/transformation.
    - An EvalSet is a collection of Evals
    - A Configuration provides an interface with the hardware environment.

    Pydantic models:
    flexeval.schema.Config
        Multithreading details
        Environment file and other environment variables.
        Log outputs.
    Eval
        Operations to perform
            Rubrics
                RubricLookup
                    Rubric name
                    Override: Place(s) to look it up
                Rubric
                    Template
                    Mapping
                    Metadata

            Rubric names OR Rubrics
                Rubric
                    Template
                    Mapping
                    Metadata (name, version, notes, etc.)
            Function names VERSUS Functions
        
    EvalRun
        Input data sources
        Output data path
        Eval
        Config
        Where it looks for the rubrics and the functions by name.


    EvalSet
        DEPRECATED
        collection of Evals
        Can be run wtih different input/output files...
    
    Database objects:
    EvalSetRun
        Particular job instance
