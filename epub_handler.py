import hashlib
import html
import os
import re
import logging
import time
import json
import random
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag, Comment, Doctype, ProcessingInstruction
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Set
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from translator_base import TranslatorBase
from undetected_chromedriver import Chrome, ChromeOptions
from deepl_translator import DeepLTranslator

TEXT_DELIMITER = "|||---|||"
logger = logging.getLogger(__name__)

class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "checkpoints", checkpoint_file: str = "translation_checkpoint.json"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self.checkpoint_file = os.path.join(self.checkpoint_dir, checkpoint_file)
        self.checkpoint_data = {}
        self.logger = logging.getLogger(__name__)
        self._load_checkpoint()
        
    def _load_checkpoint(self) -> None:
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    self.checkpoint_data = json.load(f)
                self.logger.info(f"Checkpoint loaded from {self.checkpoint_file}")
            else:
                self.logger.info("No checkpoint file found.")
                self.checkpoint_data = {}
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"Failed to load checkpoint: {e}. Starting fresh.")
            self.checkpoint_data = {}
            
    def save_checkpoint(self, checkpoint_key: str, item_id: str, chunk_key: str, line_index: int, line_data: dict):
        """Saved a single translated line to the checkpoint."""
        try:
            # Ensuring the nested dictionary structure exists
            item_data = self.checkpoint_data.setdefault(checkpoint_key, {}).setdefault(item_id, {'lines': {}})
            lines = item_data['lines']
            
            lines[f"{chunk_key}_line{line_index}"] = json.dumps(line_data)
            
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Checkpoint saved for: {item_id}, line: {chunk_key}_line{line_index}")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint for line: {e}")
    
    def set_completed(self, checkpoint_key: str, item_id: str):
        """Marks an entire item (XHTML file) as completed."""
        try:
            self.checkpoint_data.setdefault(checkpoint_key, {}).setdefault(item_id, {})['completed'] = True
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Marked item as completed: {item_id}")
        except Exception as e:
            self.logger.error(f"Failed to set completed status for {item_id}: {e}")
            
class EPUBTranslator:
    def __init__(self, source_lang: str, target_lang: str, browser: Optional[webdriver.Chrome] = None):
        self.logger = logging.getLogger(__name__)
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.book = None
        # XHTML files containing these words will be excluded from translation process
        self.excluded_keywords = ['toc', 'nav', 'cover', 'title', 'index', 'info', 'copyright']
        self.total_sections  = 0
        self.current_section = 0
        self.browser = browser
        self.checkpoint_manager = CheckpointManager()
    
    def load_epub(self, filepath: str) -> bool:
        try:
            self.logger.info(f"Loading EPUB: {filepath}")
            self.book = epub.read_epub(filepath)
            self.total_sections = len(self.get_content_items())
            if self.total_sections == 0:
                raise ValueError("No content sections found in EPUB")
            self.logger.info(f"Found {self.total_sections} content sections")
            self.checkpoint_manager._load_checkpoint()
            return True
        except Exception as e:
            self.logger.error(f"Failed to load EPUB: {e}", exc_info=True)
            return False
        
    def get_content_items(self) -> List:
        content_items = []
        
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                if not any(keyword in item.get_name().lower() for keyword in self.excluded_keywords):
                    content_items.append(item)
        return content_items
    
    def extract_translatable_nodes(self, soup: BeautifulSoup) -> List[NavigableString]:
        """Finds ands reutrn a list of all individual text nodes that should be translated."""
        text_nodes = []
        body = soup.find('body')
        
        if not body:
            return []
        
        for element in body.find_all(string=True):
            if element.parent.name not in ['script', 'style', 'title'] and str(element).strip():
                text_nodes.append(element)
        return text_nodes
            
    def intelligent_chunk_text(self, text_list: List[str], max_chars: int) -> List[str]:
        """
        Groups a list of strings into larger chunks for translation.
        """
        
        if not text_list: return []
        
        chunks = []
        current_chunk_list = []
        current_len = 0
        
        for text in text_list:
            if current_len + len(text) + len(TEXT_DELIMITER) > max_chars and current_chunk_list:
                chunks.append(TEXT_DELIMITER.join(current_chunk_list))
                current_chunk_list = [text]
                current_len = len(text)
            else:
                current_chunk_list.append(text)
                current_len += len(text) + len(TEXT_DELIMITER)
            
        if current_chunk_list:
            chunks.append(TEXT_DELIMITER.join(current_chunk_list))
            
        return chunks
    
    def translate_epub(self, output_path: str, translator: TranslatorBase, progress_callback: Optional[Callable] = None, stop_flag: Optional[Callable] = None) -> bool:
        try:
            if not self.book: raise ValueError("No EPUB loaded")
            content_items = self.get_content_items()
            temp_output_path = output_path + "_temp.epub"
            os.makedirs(os.path.dirname(temp_output_path), exist_ok=True)
            
            if isinstance(translator, DeepLTranslator):
                if not translator.set_languages(self.source_lang, self.target_lang):
                    raise Exception("Failed to set languages in DeepL.")
                
            for i, item in enumerate(content_items):
                if stop_flag and stop_flag(): return False
                
                self.current_section = i + 1
                item_id = item.get_id()
                self.logger.info(f"Processing section {self.current_section}/{self.total_sections}: {item.get_name()}")
                
                checkpoint_key = f"{str(Path(output_path).parent / Path(output_path).stem)}_{item_id}"
                item_data = self.checkpoint_manager.checkpoint_data.get(checkpoint_key, {}).get(item_id, {})
                
                if item_data and item_data.get('completed', False):
                    self.logger.info(f"Skipping already completed section: {item_id}")
                    if progress_callback: progress_callback((i + 1)/ self.total_sections * 100)
                    continue
                
                content = item.get_content().decode('utf-8')
                soup = BeautifulSoup(content, 'html.parser')
                
                #1. Extract all individual text nodes that need translation.
                body = soup.find('body')
                
                original_text_nodes = [
                    node for node in body.find_all(string=True)
                    if node.parent.name not in ['script', 'style', 'title'] and str(node).strip()
                ]
                
                if not original_text_nodes:
                    self.logger.info(f"No translatable text in {item.get_name()}.")
                    self.checkpoint_manager.set_completed(checkpoint_key, item_id)
                    continue
                
                # 2. Check the checkpoint for existing translations.
                checkpoint_lines = item_data.get('lines', {})
                texts_to_translate = []
                # Keep a map of the original index for each text we send for translation.
                untranslated_indices_map = {}
                
                for idx, node in enumerate(original_text_nodes):
                    line_key = f"chunk0_line{idx}"
                    if line_key not in checkpoint_lines:
                        # Store the original index this text corresponds to.
                        untranslated_indices_map[len(texts_to_translate)] = idx
                        texts_to_translate.append(str(node).strip())
                
                # 3. Translate only what's necessary, in chunks.
                if texts_to_translate:
                    self.logger.info(f"Found {len(texts_to_translate)} untranslated segments.")
                    text_chunks = self.intelligent_chunk_text(texts_to_translate, translator.max_input_length)
                    
                    chunk_start_index = 0
                    newly_translated_lines = []
                    
                    for j, chunk in enumerate(text_chunks):
                        if stop_flag and stop_flag(): break
                        self.logger.info(f"Translating chunk {j + 1}/{len(text_chunks)}...")

                        translated_chunk = translator._translate_chunk_with_verification(chunk, stop_flag=stop_flag)
                        translated_chunk = re.sub(r'Translated with DeepL\.com \(free version\)', '', translated_chunk).strip()                  
                
                        if "[[TRANSLATION FAILED" in translated_chunk:
                            translated_chunk = chunk
                        
                        newly_translated_lines.extend(translated_chunk.split(TEXT_DELIMITER))
                            
                    # 4. Align and save new translations to the checkpoint.
                    if len(newly_translated_lines) == len(texts_to_translate):
                        for new_idx, translated_text in enumerate(newly_translated_lines):
                            original_idx = untranslated_indices_map[new_idx]
                            is_dialogue = bool(re.match(r'^\s*["“‘]', translated_text.strip()))
                            line_data = {'text': translated_text, 'is_dialogue': is_dialogue}
                            self.checkpoint_manager.save_checkpoint(checkpoint_key, item_id, f"chunk{j}", original_idx, line_data)
                    else:
                        self.logger.error(f"CRITICAL ALIGNMENT FAILURE in {item_id}. Original count: {len(texts_to_translate)}, translated count: {len(newly_translated_lines)}. Skipping this section.")
                        continue # Skip to next file
                
                # 5. Reconstruct HTML by replacing nodes using the complete checkpoint data.
                final_checkpoint_lines = self.checkpoint_manager.checkpoint_data[checkpoint_key][item_id]['lines']
                
                for idx, node in enumerate(original_text_nodes):
                    line_key = f"chunk0_line{idx}"
                    
                    if line_key in final_checkpoint_lines:
                        line_data = json.loads(final_checkpoint_lines[line_key])
                        translated_text = line_data['text']
                        is_dialogue = line_data['is_dialogue']
                        
                        # Preserve surrounding whitespace
                        original_string = str(node)
                        leading_space = ' ' if original_string.startswith(' ') else ''
                        trailing_space = ' ' if original_string.endswith(' ') else ''
                        final_text = f"{leading_space}{translated_text}{trailing_space}"
                        
                        if is_dialogue and node.parent.name == 'p':
                            em_tag = soup.new_tag('em')
                            em_tag.string = final_text
                            node.replace_with(em_tag)
                        else:
                            node.replace_with(NavigableString(final_text))
                        
                html_tag = soup.find('html')
                if html_tag: html_tag['lang'] = self.target_lang
                item.set_content(str(soup).encode('utf-8'))
                
                self._save_intermediate_epub(temp_output_path)
                self.checkpoint_manager.set_completed(checkpoint_key, item_id)
                if progress_callback: progress_callback((i + 1) / self.total_sections * 100)
            
            self._save_final_epub(output_path)
            if os.path.exists(temp_output_path): os.remove(temp_output_path)
            return True
                
        except Exception as e:
            self.logger.error(f'EPUB translation failed: {e}', exc_info=True)
        
    def reconstruct_html(self, soup: BeautifulSoup, all_nodes: List[NavigableString], translated_data: Dict[str, Dict]):
        """
        Reconstructs the HTML by directly modifying the soup object.
        This is the most robust method.
        """
        for idx, node in enumerate(all_nodes):
            line_key = f"chunk0_line{idx}"
            
            if line_key in translated_data:
                line_info = translated_data[line_key]
                translated_text = line_info['text']
                is_dialogue = line_info['is_dialogue']
                
            # Preserve original whitespace
            original_string = str(node)
            leading_space = ' ' if original_string.startswith(' ') else ''
            trailing_space = ' ' if original_string.endswith(' ') else ''
            final_text = f"{leading_space}{translated_text}{trailing_space}"
            
            # Dialogue Styling
            # Check if node is already in an <em> or <i> tag.
            if node.parent.name in ['em', 'i']:
                # If so, just replace the text content.
                node.replace_with(NavigableString(final_text))
            elif is_dialogue:
                # If it's a dialogue and not already italicized, wrap it.
                em_tag = soup.new_tag('em')
                em_tag.string = final_text
                node.replace_with(em_tag)
            else:
                # Otherwise, it's plain text
                node.replace_with(NavigableString(final_text))
                            
    def _save_intermediate_epub(self, filepath: str):
        try:
            epub.write_epub(filepath, self.book)
            self.logger.info(f"Intermediate EPUB saved: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save Intermediate EPUB: {e}")
            raise
        
    def _save_final_epub(self, filepath: str):
        try:
            epub.write_epub(filepath, self.book)
            self.logger.info(f"Final EPUB saved: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save final EPUB: {e}")
            raise
        
    def setup_browser(self, chromedriver_path: str) -> Chrome:
        try:
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument(f"--user-data-dir={os.path.join(os.getcwd(), 'chrome_profile_deepl')}")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            driver = Chrome(options=chrome_options, executable_path=chromedriver_path)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.browser = driver
            self.logger.info("Browser set up successfully with undetected_chromedriver for DeepL.")
            return driver
        except Exception as e:
            self.logger.error(f"Failed to set up browser: {e}")
            raise
            
    def wait_for_manual_login(self, url: str, timeout: int = 60):
        try:
            self.browser.get(url)
            # Check for presence of profile button
            WebDriverWait(self.browser, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="menu-account-in-btn"]'))
            )
            self.logger.info("Login detected (via DeepL-specific element).")
            return True
        except Exception as e:
            self.logger.error(f"Login error: {e}")
            return False
            
    def cleanup(self):
        self.book = None
        self.total_sections = 0
        self.current_section = 0
        if self.browser:
            try:
                self.browser.quit()
            except Exception as e:
                self.logger.warning(f"Error during browser cleanup: {e}")
        self.browser = None