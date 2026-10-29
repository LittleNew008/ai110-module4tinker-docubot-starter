"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import re
import glob

# Common words that say nothing about the topic of a question. They are
# ignored when scoring, otherwise "the" or "is" alone could make an
# unrelated section look relevant.
STOP_WORDS = frozenset(
    "a an and any all are as at be by do does for how i in is it of on or "
    "our so that the there these this to was what when where which who with".split()
)

# Evidence threshold: a section only counts as relevant if the topic words
# from the query appear in it at least this many times. A single stray match
# is more likely coincidence than an answer.
MIN_SCORE = 2

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split documents into heading sections, the unit of retrieval
        self.sections = self.split_into_sections(self.documents)  # List of (filename, text)

        # Build a retrieval index over the sections (implemented in Phase 1)
        self.index = self.build_index(self.sections)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Section Splitting
    # -----------------------------------------------------------

    @staticmethod
    def split_into_sections(documents):
        """
        Splits each document at its markdown headings (lines starting with #).
        A section is a heading plus everything up to the next heading.
        Any text before the first heading becomes its own section.
        Returns a list of tuples: (filename, section_text)
        """
        sections = []
        for filename, text in documents:
            current = []
            in_fence = False
            for line in text.splitlines():
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                is_heading = not in_fence and re.match(r"#{1,6}\s", line)
                if is_heading and current:
                    sections.append((filename, "\n".join(current).strip()))
                    current = []
                current.append(line)
            if current:
                sections.append((filename, "\n".join(current).strip()))
        return [(f, s) for f, s in sections if s]

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    @staticmethod
    def tokenize(text):
        """
        Lowercases text and splits it into words, dropping punctuation.
        Underscores are kept so names like AUTH_SECRET_KEY stay whole.
        """
        return re.findall(r"[a-z0-9_]+", text.lower())

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the sections
        they appear in. `documents` is a list of (filename, text) pairs; each
        pair is one section, and the index stores its position in that list.

        Example structure:
        {
            "token": [3, 7],
            "database": [12]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for position, (_, text) in enumerate(documents):
            for word in set(self.tokenize(text)):
                index.setdefault(word, []).append(position)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score

        Stop words are dropped from the query first, so only topic words count.
        """
        query_words = set(self.tokenize(query)) - STOP_WORDS
        return sum(1 for word in self.tokenize(text) if word in query_words)

    def retrieve(self, query, top_k=3):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Each snippet is one heading section of a document, not the whole file.
        Return a list of (filename, section_text) sorted by score descending.

        Sections scoring below MIN_SCORE are not evidence, so they are dropped.
        If nothing is left, this returns [] and both answer modes reply
        "I do not know based on these docs." (RAG mode never calls the LLM).
        """
        # Use the index to narrow down to sections sharing at least one topic word
        candidates = set()
        for word in set(self.tokenize(query)) - STOP_WORDS:
            candidates.update(self.index.get(word, []))

        results = []
        for position in sorted(candidates):
            filename, text = self.sections[position]
            score = self.score_document(query, text)
            if score >= MIN_SCORE:
                results.append((score, filename, text))

        results.sort(key=lambda item: item[0], reverse=True)
        return [(filename, text) for _, filename, text in results[:top_k]]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
