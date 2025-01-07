import os
import pickle
import chromadb
from chromadb.config import Settings
from typing import Optional, Union


class StringSimilarityMap:
    """
    Provides string-pair storage and retrieval using a vector database.
    Each DB entry is a pair of strings: an input string and an output string.
    The input string is embedded and used as the retrieval key.
    The output string can be anything, but it's typically used as a dict key.
    Vector embeddings are currently supplied by Chroma's default Sentence Transformers.
    """

    def __init__(
        self,
        verbosity: Optional[int] = 0,
        reset: Optional[bool] = False,
        path_to_db_dir: Optional[str] = None,
    ):
        """
        Args:
            - verbosity (Optional, int): 1 to print memory operations, 0 to omit them. 3+ to print string-pair lists.
            - reset (Optional, bool): True to clear the DB before starting. Default False.
            - path_to_db_dir (Optional, str): path to the directory where the DB is stored.
        """
        self.verbosity = verbosity
        self.path_to_db_dir = path_to_db_dir

        # Load or create the vector DB on disk.
        settings = Settings(
            anonymized_telemetry=False, allow_reset=True, is_persistent=True, persist_directory=path_to_db_dir
        )
        self.db_client = chromadb.Client(settings)
        self.vec_db = self.db_client.create_collection("string-pairs", get_or_create=True)  # The collection is the DB.

        # Load or create the associated string-pair dict on disk.
        self.path_to_dict = os.path.join(path_to_db_dir, "uid_text_dict.pkl")
        self.uid_text_dict = {}
        self.last_string_pair_id = 0
        if (not reset) and os.path.exists(self.path_to_dict):
            print("\nLOADING STRING SIMILARITY MAP FROM DISK  {}".format(self.path_to_dict))
            print("    Location = {}".format(self.path_to_dict))
            with open(self.path_to_dict, "rb") as f:
                self.uid_text_dict = pickle.load(f)
                self.last_string_pair_id = len(self.uid_text_dict)
                print("\n{} STRING PAIRS LOADED".format(len(self.uid_text_dict)))
                if self.verbosity >= 3:
                    self.list_string_pairs()

        # Clear the DB if requested.
        if reset:
            self.reset_db()

    def list_string_pairs(self):
        """Prints the string-pair contents."""
        print("LIST OF STRING PAIRS")
        for uid, text in self.uid_text_dict.items():
            input_text, output_text = text
            print("  ID: {}\n    INPUT TEXT: {}\n    OUTPUT TEXT: {}".format(uid, input_text, output_text))

    def save_string_pairs_to_text_files(self):
        """Saves the contents to text files."""
        # Delete all files in mem_text dir.
        for file in os.listdir("mem_text"):
            os.remove(os.path.join("mem_text", file))

        print("LIST OF STRING PAIRS")
        for uid, text in self.uid_text_dict.items():
            input_text, output_text = text
            print("  ID: {}\n    INPUT TEXT: {}\n    OUTPUT TEXT: {}".format(uid, input_text, output_text))
            # Save the input string to a file with the same name as the string-pair ID in the mem_text dir, which is a subdir of the dir containing this file.
            with open("mem_text/{}.txt".format(uid), "w") as file:
                file.write("  ID: {}\n    INPUT TEXT: {}\n    OUTPUT TEXT: {}".format(uid, input_text, output_text))

    def save_string_pairs(self):
        """Saves self.uid_text_dict to disk."""
        with open(self.path_to_dict, "wb") as file:
            pickle.dump(self.uid_text_dict, file)

    def reset_db(self):
        """Forces immediate deletion of the DB's contents, in memory and on disk."""
        print("\nCLEARING STRING-PAIR MAP")
        self.db_client.delete_collection("string-pairs")
        self.vec_db = self.db_client.create_collection("string-pairs")
        self.uid_text_dict = {}
        self.save_string_pairs()

    def add_input_output_pair(self, input_text: str, output_text: str):
        """Adds an input-output pair to the vector DB."""
        self.last_string_pair_id += 1
        self.vec_db.add(documents=[input_text], ids=[str(self.last_string_pair_id)])
        self.uid_text_dict[str(self.last_string_pair_id)] = input_text, output_text
        if self.verbosity >= 1:
            print("\nINPUT-OUTPUT PAIR ADDED TO VECTOR DATABASE:\n  ID\n    {}\n  INPUT\n    {}\n  OUTPUT\n    {}\n".format(
                        self.last_string_pair_id, input_text, output_text))
        if self.verbosity >= 3:
            self.list_string_pairs()

    def get_related_string_pairs(self, query_text: str, n_results: int, threshold: Union[int, float]):
        """Retrieves STRING PAIRS that are related to the given query text within the specified distance threshold."""
        if n_results > len(self.uid_text_dict):
            n_results = len(self.uid_text_dict)
        if n_results > 0:
            results = self.vec_db.query(query_texts=[query_text], n_results=n_results)
            num_results = len(results["ids"][0])
        else:
            num_results = 0
        string_pairs = []
        for i in range(num_results):
            uid, input_text, distance = results["ids"][0][i], results["documents"][0][i], results["distances"][0][i]
            if distance < threshold:
                input_text_2, output_text = self.uid_text_dict[uid]
                assert input_text == input_text_2
                if self.verbosity >= 1:
                    print("\nINPUT-OUTPUT PAIR RETRIEVED FROM VECTOR DATABASE:\n  INPUT1\n    {}\n  OUTPUT\n    {}\n  DISTANCE\n    {}".format(
                        input_text, output_text, distance))
                string_pairs.append((input_text, output_text, distance))
        return string_pairs
