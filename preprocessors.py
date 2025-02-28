import os
import re
import string
import sys
from bs4 import BeautifulSoup
from ebooklib import epub
import ebooklib

class TextIn:
    def __init__(self, source, start, end, skiplinks, debug, title, author, chapters_per_file=1, customwords="custom_words.txt"):
        self.source = source
        self.bookname = os.path.splitext(os.path.basename(source))[0]
        self.start = start - 1
        self.end = end
        self.skiplinks = skiplinks
        self.debug = debug
        self.chapters = []
        self.chapters_to_read = []
        self.chapters_per_file = chapters_per_file
        self.customwords = customwords
        self.title = title
        self.author = author
        self.pronunciation = self.set_custom_dict()

        # Automatically create the clean_text directory
        self.clean_text_dir = "clean_text"
        os.makedirs(self.clean_text_dir, exist_ok=True)
        
        # Set up the source and automatically process chapters if EPUB
        if source.endswith('.epub'):
            self.book = epub.read_epub(source)
            self.sourcetype = 'epub'
            self.get_chapters_epub()  # Automatically execute get_chapters_epub
        elif source.endswith('.txt'):
            self.sourcetype = 'txt'
        else:
            print("Can only handle epub or txt as source.")
            sys.exit()

    def get_chapters_epub(self):
        '''
            Class function for text processing
            Dependency: chap2text, prep_text, apply_customwords
            Packages required: ebooklib 
        '''
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self.chapters.append(item.get_content())

        for i in range(len(self.chapters)):
            if i <= 1:  # Skip chapters -1 and 0 (title and summary chapters)
                continue

            # Process and clean the chapter text
            text = self.chap2text(self.chapters[i])
            text = self.prep_text(text)
            text = self.apply_customwords(text)
            if len(text) < 150:
                # Skip chapters too short to process
                continue

            self.chapters_to_read.append((i, text))  # Append chapter number and text for later use

        if self.end == 999:
            self.end = len(self.chapters_to_read)

        # Combine chapters into files based on chapters_per_file
        self.save_combined_chapters()

    def save_combined_chapters(self):
        '''
            Combines chapters and saves them to files.
        '''
        for i in range(0, len(self.chapters_to_read), self.chapters_per_file):
            chunk = self.chapters_to_read[i:i + self.chapters_per_file]
            start_chapter = chunk[0][0]
            end_chapter = chunk[-1][0]
            combined_text = "\n\n".join(chapter[1] for chapter in chunk)
            self.save_chapter_to_file(start_chapter, end_chapter, combined_text)

    def save_chapter_to_file(self, start_chapter, end_chapter, text):
        '''
            Saves the cleaned chapter text to a file in the clean_text directory with a description.
        '''
        filename = os.path.join(self.clean_text_dir, f"{self.bookname}_chapters_{start_chapter}_to_{end_chapter}.txt")
        
        # Add a description and save the file
        description = self.add_description(start_chapter, end_chapter)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(description + "\n\n" + text)
        
        print(f"Chapters {start_chapter} to {end_chapter} saved as {filename}.")

    def add_description(self, start_chapter, end_chapter):
        '''
            Generates a description to be added at the top of each chapter text file.
        '''
        if start_chapter == end_chapter:
            description = (
                f"Welcome to the Wizarding Wireless America channel. In this episode we will be reading {self.title} chapter {start_chapter - 1} by {self.author}. We have been making constant improvements to our model and reader capabilities. We hope you enjoy this episode. All credit for this work goes to {self.author}. Please see their work at the Archive of Our Own webpage."
            )
        else:
            description = (
                f"Welcome to the Wizarding Wireless America channel. In this episode we will be reading {self.title} chapters {start_chapter - 1} to {end_chapter -1} by {self.author}. We have been making constant improvements to our model and reader capabilities. We hope you enjoy this episode. All credit for this work goes to {self.author}. Please see their work at the Archive of Our Own webpage."
            )
        return description

    def apply_customwords(self, text):    
        '''
            Referenced by get_chapters_epub
            Dependency: set_custom_dict
            Packages required: re
        '''
        def replace_word(match):
            word = match.group(0)
            clean_word = re.sub(r'[^\w\s]', '', word.lower())
            return self.pronunciation.get(clean_word, word)
        
        modified_text = re.sub(r'\b\w+\b', replace_word, text)
        return modified_text
    def expand_abbreviations(self, text):
        '''
            Expands common abbreviations in text.
        '''
        text = re.sub(r'\bMr\.\s', 'Mister ', text)
        text = re.sub(r'\bMrs\.\s', 'Missus ', text)
        text = re.sub(r'\bMs\.\s', 'Miss ', text)
        text = re.sub(r'\bSt\.\s', 'Saint ', text)
        return text
    
    def prep_text(self, text):
        '''
            Basic text cleaner for TTS operations
            Referenced by: get_chapters_epub
            Packages required: re
        '''
        # Expand abbreviations
        text = self.expand_abbreviations(text)
    
        # Additional replacements and cleanups
        text = text.replace("—", ", ").replace("--", ", ").replace(";", ", ").replace(":", ", ").replace("''", ", ")
        text = (
            text.replace("--", ", ")
            .replace("—", ", ")
            .replace(";", ", ")
            .replace(":", ", ")
            .replace("''", ", ")
            .replace("’", "'")
            .replace('“', '"')
            .replace('”', '"')
            .replace("◇", "")
            .replace(" . . . ", ", ")
            .replace("... ", ", ")
            .replace("«", " ")
            .replace("»", " ")
            .replace("[", "")
            .replace("]", "")
            .replace("&", " and ")
            .replace(" GNU ", " new ")
            .replace("\n", " \n")
            .replace("*", " ")
            .strip()
        )
        allowed_chars = string.ascii_letters + string.digits + "-,.!?' "
        text = ''.join(c for c in text if c in allowed_chars)
        return text

    

    def chap2text(self, chap):
        '''
            Converts the XML structure of epubs to chapter text.
            Referenced by get_chapters_epub
            Packages required: BeautifulSoup
        '''
        blacklist = ['[document]', 'noscript', 'header', 'html', 'meta', 'head', 'input', 'script']
        output = ''
        soup = BeautifulSoup(chap, 'html.parser')
        if self.skiplinks:
            for a in soup.findAll('a', href=True):
                a.extract()

        for a in soup.findAll('a', href=True):
            if a.text.isdigit():
                a.extract()
                
        text = soup.find_all(string=True)
        for t in text:
            if t.parent.name not in blacklist:
                output += '{} '.format(t)
                
        return output           

    def set_custom_dict(self):
        '''
            Referenced by class init
            Dependency: None
        ''' 
        pronunciation_dict = {}
        with open(self.customwords, 'r') as f:
            for line in f:
                word, pronunciation = line.strip().split('|', maxsplit=1)
                pronunciation_dict[word.lower()] = pronunciation
        return pronunciation_dict
