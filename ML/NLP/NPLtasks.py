"""
NPLtasks.py

This module defines the NPLtasks class, which provides methods for basic Natural Language Processing (NLP) tasks using the spaCy library.

Classes:
    NPLtasks: A class that encapsulates basic NLP tasks such as text elaboration, token retrieval, and text slicing.

Usage example:
    tasks = NPLtasks()
    doc = tasks.elaborate_text("Hello, world!")
    print(f"The doc.text is: {doc.text}")
    print(f"The first token is: {tasks.get_token_text(doc, 0)}")
    print(f"The slice text is: {tasks.get_slice_text(doc, 0, 2)}")
"""

import spacy
from tabulate import tabulate


class NPLtasks:
    def __init__(self):
        """
        Initializes the NPLtasks class with a blank English spaCy model.
        """
        self.nlp = {
            "nlp_en": spacy.blank("en"),
            "nlp_en_core_web_sm": spacy.load("en_core_web_sm"),
        }

    def elaborate_text(self, text):
        """
        Processes the given text and returns a spaCy Doc object.

        Parameters:
            text (str): The text to be processed.

        Returns:
            spacy.tokens.Doc: The processed Doc object.
        """
        doc = self.nlp["nlp_en"](text)
        return doc

    def get_token_text(self, doc, index):
        """
        Retrieves the text of a token at a specified index in the Doc.

        Parameters:
            doc (spacy.tokens.Doc): The Doc object containing the tokens.
            index (int): The index of the token to retrieve.

        Returns:
            str: The text of the token at the specified index.
        """
        return doc[index].text

    def get_slice_text(self, doc, start, end):
        """
        Retrieves the text of a slice of tokens from the Doc.

        Parameters:
            doc (spacy.tokens.Doc): The Doc object containing the tokens.
            start (int): The starting index of the slice.
            end (int): The ending index of the slice.

        Returns:
            str: The text of the slice of tokens.
        """
        return doc[start:end].text

    def predicting_part_of_speech(self, text):
        """
        Predicts the part of speech tags for the tokens in the given text.

        Parameters:
            text (str): The text for which to predict part of speech tags.

        Returns:
            list: A list of tuples containing the token text and its predicted part of speech tag.
        """
        doc = self.nlp["nlp_en_core_web_sm"](text)
        pos_tags = [(token.text, token.pos_) for token in doc]
        return pos_tags

    def predicting_named_entities(self, text):
        """
        Predicts the named entities in the given text and displays token-level information.

        Parameters:
            text (str): The text for which to predict named entities.

        Returns:
            str: A formatted table containing token information and named entities.
        """
        doc = self.nlp["nlp_en_core_web_sm"](text)

        named_entities = [(ent.text, ent.label_) for ent in doc.ents]

        token_info = []
        for token in doc:
            token_info.append((token.text, token.pos_, token.dep_))

        table_tokens = tabulate(
            token_info, headers=["Token", "POS", "Dependency"], tablefmt="grid"
        )
        table_entities = tabulate(
            named_entities, headers=["Entity", "Label"], tablefmt="grid"
        )

        return f"Named Entities:\n{table_entities}\n\nToken Information:\n{table_tokens}"

 
__init__ = NPLtasks()
doc = __init__.elaborate_text("Hello, world!")
print(f"The doc.text is: {doc.text}")
print(f"The first token is: {__init__.get_token_text(doc, 0)}")
print(f"The slice text is: {__init__.get_slice_text(doc, 0, 2)}")
print(f"The part of speech tags are: {__init__.predicting_part_of_speech('Hello, world!')}")
print(f"The part of speech tags are: {__init__.predicting_named_entities('It’s official: Apple is the first U.S. public company to reach a $1 trillion market value)')}")

