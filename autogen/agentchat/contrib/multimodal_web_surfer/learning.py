
class Learning():
    """
    This learning component is designed to boost an agent's task-completion performance.
    Learning consists of using long-term memory (a vector database) to:
    1. Store task-relevant experience, like actions and their results.
    2. Recall task-relevant advice, for inclusion into the agent's prompt.
    """
    def __init__(
        self,
        verbosity: Optional[int] = 0,
        reset_db: Optional[bool] = False,
        path_to_db_dir: Optional[str] = "./tmp/teachable_agent_db",
        recall_threshold: Optional[float] = 1.5,
        max_num_retrievals: Optional[int] = 10,
        llm_config: Optional[Union[Dict, bool]] = None,
    ):
        """
        Args:
            verbosity (Optional, int): # 0 (default) for basic info, 1 to add memory operations, 2 for analyzer messages, 3 for memo lists.
            reset_db (Optional, bool): True to clear the DB before starting. Default False.
            path_to_db_dir (Optional, str): path to the directory where this particular agent's DB is stored. Default "./tmp/teachable_agent_db"
            recall_threshold (Optional, float): The maximum distance for retrieved memos, where 0.0 is exact match. Default 1.5. Larger values allow more (but less relevant) memos to be recalled.
            max_num_retrievals (Optional, int): The maximum number of memos to retrieve from the DB. Default 10.
            llm_config (dict or False): llm inference configuration passed to TextAnalyzerAgent.
                If None, TextAnalyzerAgent uses llm_config from the teachable agent.
        """
        self.verbosity = verbosity
        self.path_to_db_dir = path_to_db_dir
        self.recall_threshold = recall_threshold
        self.max_num_retrievals = max_num_retrievals
        self.llm_config = llm_config

        self.analyzer = None
        self.teachable_agent = None

        # Create the memo store.
        # self.memo_store = MemoStore(self.verbosity, reset_db, self.path_to_db_dir)

    def update_memory(self):
        # Don't do anything yet.
        pass
        return

    def include_advice(self, text_prompt):
        # Don't do anything yet.
        pass
        return text_prompt

