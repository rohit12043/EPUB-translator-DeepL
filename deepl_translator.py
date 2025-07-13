import logging
import threading
import time
import random
import re
from typing import List, Tuple, Dict, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, JavascriptException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement
from tkinter import messagebox

from translator_base import TranslatorBase

logger = logging.getLogger(__name__)

class DeepLTranslator(TranslatorBase):
    max_input_length = 4950
    
    LANG_MAP = {
        'auto': 'auto',
        'bulgarian': 'bg',
        'chinese (simplified)': 'zh',
        'czech': 'cs',
        'danish': 'da',
        'dutch': 'nl',
        'english': 'en', # We'll let DeepL pick US/UK variant
        'estonian': 'et',
        'finnish': 'fi',
        'french': 'fr',
        'german': 'de',
        'greek': 'el',
        'hungarian': 'hu',
        'indonesian': 'id',
        'italian': 'it',
        'japanese': 'ja',
        'korean': 'ko',
        'latvian': 'lv',
        'lithuanian': 'lt',
        'norwegian': 'nb',
        'polish': 'pl',
        'portuguese': 'pt', # We'll let DeepL pick Brazil/Portugal
        'romanian': 'ro',
        'russian': 'ru',
        'slovak': 'sk',
        'slovenian': 'sl',
        'spanish': 'es',
        'swedish': 'sv',
        'turkish': 'tr',
        'ukrainian': 'uk',
        'vietnamese': 'vi'
    }
    
    def __init__(self, driver, human_delay, mimic_behaviour=False, **kwargs):
        self.driver = driver
        self.human_delay = human_delay
        self.mimic_behaviour = mimic_behaviour
        self.is_logged_in = False
        self.processing_lock = threading.lock()
        
        self.last_used_time = 0
        self.cooldown = 2
        self.retry_attempts = 3
        self.base_timeout = 60
        
        self.logger = logging.getLogger(__name__)
        logger.debug("DeepLTranslator Initialized")
        
    def set_languages(self, source_lang: str, target_lang: str):
        """Sets the source and target languages on the DeepL website"""
        try:
            logger.info(f"Setting languages: Source='{source_lang}', Target='{target_lang}'")
            source_code = self.LANG_MAP[source_lang.lower(), 'auto']
            target_code = self.LANG_MAP[target_lang.lower()]
            
            if not target_code:
                raise ValueError(f"Target langauge '{target_lang}' is not supported.")
            
            def select_language(dropdown_btn_selector: str, lang_code: str, lang_name: str):
                dropdown_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, dropdown_btn_selector))
                )
                dropdown_button.click()
                self.human_delay(0.3, 0.6)
                
                panel_id = dropdown_button.get_attribute("aria-controls")
                if panel_id:
                    WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, panel_id)))
                else:
                    time.sleep(1)
                    
                # using '^=' to match any test-id that STARTS with the language code
                # Handles regional variants like 'en-US'
                lang_button_selector = f'button[data-testid^="translator-lang-option-{lang_code}"]'
                
                lang_button = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, lang_button_selector)))
                
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lang_button)
                self.human_delay(0.3, 0.6)
                
                WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, lang_button_selector))).click()
                
                logger.info(f"Successfully set language to '{lang_name}' ({lang_code})")
                self.human_delay(0.5, 1)
                
                select_language('[data-testid="translator-source-lang-btn"]', source_code, source_lang)
                select_language('[data-testid="translator-target-lang-btn"]', target_code, target_lang)
                
                return True
        
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"failed to set languages: {e}", exc_info=True)
            messagebox.showerror("Error", "Could not set the languages on the DeepL page. The page structure may have changed, or an element was not visible.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while settign languages: {e}", exc_info=True)
            return False
        
    def ensure_login(self) -> bool:
        pass
    
    def find_input_element(self) -> Optional[WebElement]:
        pass
    
    def find_output_element(self) -> Optional[WebElement]:
        pass
    
    def set_input_text(self, element: WebElement, text: str) -> bool:
        pass
    
    def dismiss_overlays_and_popups(self):
        pass
    
    def wait_for_response(self, original_text_len: int) -> Optional[str]:
        pass
    def translate_chunk_with_verification(self, chunk: str) -> str:
        pass