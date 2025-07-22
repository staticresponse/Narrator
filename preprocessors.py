import os
import re
import string
import sys
from bs4 import BeautifulSoup
from ebooklib import epub
import ebooklib
import inflect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class TextIn:
    def __init__(self, source, start, end, skiplinks, debug, title, author, chapters_per_file=1, customwords="custom_words.txt", intro="", outtro=""):

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
        self.intro = intro
        self.outtro = outtro
        logger.info(f"Initialized TextIn with source: {source}, chapters {start} to {end}")        
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
        Class function for extracting and processing chapters from EPUB in correct reading order.
        '''
        # Ensure we respect reading order
        item_map = {item.get_id(): item for item in self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT)}
        ordered_ids = [item[0] for item in self.book.spine]
        
        chapter_num = 1
        for uid in ordered_ids:
            if uid not in item_map:
                continue
            
            content = item_map[uid].get_content()
            text = self.chap2text(content)
            text = self.prep_text(text)
            text = self.apply_customwords(text)

            if len(text) < 150:
                continue

            if chapter_num - 1 < self.start or chapter_num > self.end:
                chapter_num += 1
                continue

            self.chapters_to_read.append((chapter_num, text))

            if self.debug:
                logger.info(f"Chapter {chapter_num} length: {len(text)}")

            chapter_num += 1

        if self.end == 999:
            self.end = chapter_num - 1

        self.save_combined_chapters()


    def save_combined_chapters(self):
        '''
            Combines chapters and saves them to files.
        '''
        part_number = 1  # Start part numbering from 1

        for i in range(0, len(self.chapters_to_read), self.chapters_per_file):
            chunk = self.chapters_to_read[i:i + self.chapters_per_file]
            start_chapter = chunk[0][0]
            end_chapter = chunk[-1][0]
            combined_text = "\n\n".join(chapter[1] for chapter in chunk)
            self.save_chapter_to_file(part_number, start_chapter, end_chapter, combined_text)
            part_number += 1  # Increment part number

    def save_chapter_to_file(self, part_number, start_chapter, end_chapter, text):
        '''
            Saves the cleaned chapter text to a file in the clean_text directory with a description.
        '''
        filename = os.path.join(self.clean_text_dir, f"{self.bookname}_part_{part_number}.txt")
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.intro + "\n\n" + text + "\n" + self.outtro)
        logger.info(f"Part {part_number} (Chapters {start_chapter} to {end_chapter}) saved as {filename}.")

    def apply_customwords(self, text):    
        '''
            Uses custom pronunciation as provided by the configuration item custom_words.txt
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
    def expand_ordinals(self, text):
        '''
            Converts ordinal numbers (e.g., 3rd, 15th, 22nd) into their word equivalents.
            Handles cases where there is an unintended space (e.g., "5 th" instead of "5th").
        '''
        p = inflect.engine()

        def replace_ordinal(match):
            number = int(match.group(1))  # Extract the numeric part
            return p.ordinal(number)  # Convert number to words (e.g., "5th" -> "fifth")

        # Fix cases where there's a space between the number and ordinal suffix
        text = re.sub(r'\b(\d+)\s*(st|nd|rd|th)\b', replace_ordinal, text)

        return text
        
    def prep_text(self, text):
        '''
        Enhanced text cleaner for TTS operations.
        - Expands abbreviations and ordinals
        - Removes repeated chapter titles and summaries
        - Applies paragraph formatting
        '''
        # --- Expand abbreviations and ordinals ---
        text = self.expand_abbreviations(text)
        text = self.expand_ordinals(text)

        # --- Normalize smart quotes ---
        text = (
            text.replace('’', "'")
                .replace('‘', "'")
                .replace('“', '"')
                .replace('”', '"')
        )

        # --- Clean and replace punctuation ---
        text = text.replace("—", ", ").replace("--", ", ").replace(";", ", ").replace(":", ", ").replace("''", ", ")
        text = (
            text.replace("◇", "")
                .replace(" . . . ", ", ")
                .replace("... ", ", ")
                .replace("«", " ")
                .replace("»", " ")
                .replace("[", "")
                .replace("]", "")
                .replace("&", " and ")
                .replace(" GNU ", " new ")
                .replace("*", " ")
                .strip()
        )

        # --- Remove first line if it's the intro ---
        lines = text.splitlines()
        if lines and "Wizarding Wireless America" in lines[0]:
            lines = lines[1:]  # Remove the intro line
        text = "\n".join(lines)

        # --- Remove non-allowed characters ---
        allowed_chars = string.ascii_letters + string.digits + "-,.!?' \n"
        text = ''.join(c for c in text if c in allowed_chars)

        # --- Add paragraph breaks after sentence punctuation ---
        text = re.sub(r'(?<=[.!?])\s+(?=[A-Z])', r'\n', text)

        return text



    

    def chap2text(self, chap):
        '''
        Extracts and flattens visible text from a chapter.
        Fixes broken line breaks in the middle of sentences.
        '''
        soup = BeautifulSoup(chap, 'html.parser')
        blacklist = ['[document]', 'noscript', 'header', 'html', 'meta', 'head', 'input', 'script', 'style']

        if self.skiplinks:
            for a in soup.find_all('a', href=True):
                a.extract()

        # Remove footnote-style anchors (digits only)
        for a in soup.find_all('a', href=True):
            if a.text.strip().isdigit():
                a.extract()

        # Extract visible strings
        texts = []
        for tag in soup.find_all(text=True):
            if tag.parent.name in blacklist:
                continue
            txt = tag.strip()
            if txt:
                texts.append(txt)

        # Join all the visible text parts
        output = ' '.join(texts)

        # Normalize whitespace: collapse multiple spaces, fix artificial newlines
        output = re.sub(r'\s+', ' ', output)

        return output.strip()


      

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