import os
import re
import string
import sys
from bs4 import BeautifulSoup
from ebooklib import epub
import ebooklib

class TextIn:
    def __init__(self, source, start, end, skiplinks, debug, customwords, title, author):
        self.source = source
        self.bookname = os.path.splitext(os.path.basename(source))[0]
        self.start = start - 1
        self.end = end
        self.skiplinks = skiplinks
        self.debug = debug
        self.chapters = []
        self.chapters_to_read = []
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
            Dependency: chapt2text, prep_text, apply_customwords
            Packages required: ebooklib 
        '''
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self.chapters.append(item.get_content())

        for i in range(len(self.chapters)):
            # Process and clean the chapter text
            text = self.chap2text(self.chapters[i])
            text = self.prep_text(text)
            text = self.apply_customwords(text)
            if len(text) < 150:
                # Skip chapters too short to process
                continue

            # Save each chapter to a separate text file with a description
            self.save_chapter_to_file(i + 1, text)
            self.chapters_to_read.append(text)  # Append the processed chapter text

        if self.end == 999:
            self.end = len(self.chapters_to_read)

    def save_chapter_to_file(self, chapter_num, text):
        '''
            Saves the cleaned chapter text to a file in the clean_text directory with a description.
        '''
        filename = os.path.join(self.clean_text_dir, f"{self.bookname}_chapter_{chapter_num}.txt")
        
        # Add a description and save the file
        description = self.add_description(chapter_num)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(description + "\n\n" + text)
        
        print(f"Chapter {chapter_num} saved as {filename}.")

    def add_description(self, chapter_num):
        '''
            Generates a description to be added at the top of each chapter text file.
        '''
        description = (
            f"Welcome to the Wizarding Wireless America channel. In this episode we will be reading {self.title} chapter {chapter_num - 2} by {self.author}. We have been making constant improvements to our model and reader capabilities. We hope you enjoy this episode. All credit for this work goes to {self.author}. Please see their work at the Archive of Our Own webpage" 
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

    def prep_text(self, text):
        '''
            Basic text cleaner for TTS operations
            Referenced by: get_chapters_epub
            Packages required: re
        '''
        text = text.replace("—", ", ").replace("--", ", ").replace(";", ", ").replace(":", ", ").replace("''", ", ")
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
