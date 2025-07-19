import logging
import threading
import time
import random
import re
from typing import Callable, List, Tuple, Dict, Optional
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
        self.processing_lock = threading.Lock()
        
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
            source_code = self.LANG_MAP.get(source_lang.lower(), 'auto')
            target_code = self.LANG_MAP.get(target_lang.lower())
            
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
            logger.error(f"An unexpected error occurred while setting languages: {e}", exc_info=True)
            return False
        
    def ensure_login(self) -> bool:
        """Ensure the user is logged in to DeepL, prompting if necessary."""
        if self.is_logged_in:
            return True

        try:
            self.driver.get("https://www.deepl.com/translator")
            
            # Check for logged-in state (user avatar button is present)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="menu-account-in-btn"]'))
                )
                logger.info("DeepL session is active (already logged in).")
                self.is_logged_in = True
                self.human_delay(1, 2)
                return True
            except TimeoutException:
                logger.warning("Not logged in to DeepL. Prompting for manual login.")
                messagebox.showinfo(
                    "Login Required",
                    "Please log in to your DeepL account in the browser. "
                    "The script will continue automatically after it detects the login."
                )
                # Wait for the user to log in, indicated by the appearance of the account button
                WebDriverWait(self.driver, 300).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="menu-account-in-btn"]'))
                )
                logger.info("DeepL login detected.")
                self.is_logged_in = True
                self.human_delay(2, 4)
                return True

        except TimeoutException:
            logger.error("Login not detected within the 5-minute timeout.")
            messagebox.showerror("Error", "Failed to detect DeepL login. Please restart and try again.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during the login process: {e}")
            messagebox.showerror("Error", f"An error occurred during login: {e}")
            return False
    
    def find_input_element(self) -> Optional[WebElement]:
        """Find the input element for entering the original text. Returns the element or None."""
        try:
            selector = 'd-textarea[data-testid="translator-source-input"] div[role="textbox"]'
            element = WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            logger.debug(f"FOund the input element with selector: {selector}")
            return element
        except TimeoutException:
            logger.error("COuld not find the DeepL input element.")
    
    def find_output_element(self) -> Optional[WebElement]:
        """Find the output element where the translated text appears. Returns the element or None."""
        try:
            selector = 'd-textarea[data-testid="translator-target-input"] div[role="textbox"]'
            element = WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            logger.debug(f"Found the output element with selector: {selector}")
            return element
        except TimeoutException:
            logger.error("COuld not find the DeepL output textarea.")
    
    def set_input_text(self, element: WebElement, text: str) -> bool:
        """Set the given text into the input element. Returns True if successful."""
        try:
            self.driver.execute_script("arguments[0].innerHTML = ''", element)
            chunk_size = 1000
            text_chunks = [text[i: i + chunk_size] for i in range(0, len(text), chunk_size)]
        
            for chunk in text_chunks:
                self.driver.execute_script("arguments[0].textContent += arguments[1]", element, chunk)
                self.human_delay(0.005, 0.1)
            
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}))", element)
            return True
        except JavascriptException as e:
            logger.error("Failed to save text using JavaScript")
            return False
        
      
    def _dismiss_overlays_and_popups(self):
            """
            Dismiss any overlays or pop-ups on the website, specifically the 'usage limit' dialog.
            This script is designed to be robust against changes in CSS class names.
            """
            
            script = r"""
                // Use a stable attribute to find the dialog's content area.
                const dialogContent = document.querySelector('[data-testid="notification-many-translations-block"]');
                let closedSomething = false;

                if (dialogContent) {
                    // Find the button by its text content, which is much more reliable.
                    // We convert the NodeList of buttons to an Array to use the .find() method.
                    const allButtons = Array.from(dialogContent.querySelectorAll('button'));
                    const backButton = allButtons.find(button => button.textContent.trim() === 'Back to Translator');

                    if (backButton) {
                        // Preferred method: click the button to trigger any intended JS events.
                        backButton.click();
                        closedSomething = true;
                    } else {
                        // Fallback method: if the button isn't found, find the top-level dialog and remove it.
                        // The top-level dialog has the role="dialog" attribute.
                        const rootDialog = document.querySelector('[role="dialog"][data-headlessui-state="open"]');
                        if (rootDialog) {
                            rootDialog.remove();
                            closedSomething = true;
                        }
                    }
                }

                // Also, attempt to remove the dark background overlay, which might be a separate element.
                // Using a "contains" selector for the class to be safe.
                const overlay = document.querySelector('div.fixed.inset-0[class*="bg-black/50"]');
                if (overlay) {
                    overlay.remove();
                    closedSomething = true;
                }

                return closedSomething;
            """
            try:
                if self.driver.execute_script(script):
                    self.logger.warning("Dismissed a 'usage limit' popup/overlay.")
                    # Wait a moment for the UI to update after the dismissal.
                    self.human_delay(0.5, 1)
            except Exception as e: # Catch a broader exception type for JS errors
                # It's common for this to fail if there's no popup, so debug level is appropriate.
                self.logger.debug(f"Could not dismiss popup (it might not have been present). JS error: {e}")
                pass
        
    
    def wait_for_response(self, original_text_len: int, stop_flag: Optional[Callable] = None) -> Optional[str]:
        """
        Wait for the translation response to stabilize, checking for a stop signal periodically.
        Returns the translated text, a stop signal, or None on timeout.
        """
        overall_timeout = self.base_timeout + (original_text_len // 80)
        start_time = time.time()
        self.logger.info("Waiting for translation to stabilize...")

        last_text = ""
        stable_cycles = 0
        required_stable_cycles = 3

        while time.time() - start_time < overall_timeout:

            if stop_flag and stop_flag():
                self.logger.warning("Stop signal detected while waiting for translation response.")

                raise InterruptedError("Translation stopped by user signal.")

            self._dismiss_overlays_and_popups()

            try:

                output_selector = 'd-textarea[data-testid="translator-target-input"] div[role="textbox"]'

                output_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, output_selector))
                )
                current_text = output_element.get_attribute('innerText').strip()
                self.logger.debug(f"Current text length: {len(current_text)}, Stable cycles: {stable_cycles}/{required_stable_cycles}")

                if current_text and current_text == last_text:
                    stable_cycles += 1
                elif current_text:
                    last_text = current_text
                    stable_cycles = 1 
                else:

                    stable_cycles = 0

                if stable_cycles >= required_stable_cycles:
                    self.logger.info(f"Translation stabilized after {time.time() - start_time:.1f}s.")
                    return current_text

                delay_end_time = time.time() + random.uniform(0.8, 1.2)
                while time.time() < delay_end_time:
                    if stop_flag and stop_flag():

                        raise InterruptedError("Translation stopped by user signal during delay.")
                    time.sleep(0.1) 

            except InterruptedError:

                raise
            except (JavascriptException, StaleElementReferenceException, TimeoutException) as e:
                self.logger.warning(f"Response check cycle interrupted by web element issue: {e}. Retrying cycle.")
                stable_cycles = 0

                recovery_delay_end_time = time.time() + random.uniform(1.5, 2.0)
                while time.time() < recovery_delay_end_time:
                    if stop_flag and stop_flag():
                        raise InterruptedError("Translation stopped by user signal during recovery delay.")
                    time.sleep(0.1)

        self.logger.error(f"Timeout of {overall_timeout}s reached waiting for stable translation.")

        return last_text if last_text else None
    
    def _translate_chunk_with_verification(self, chunk: str, stop_flag: Optional[Callable] = None) -> str:
        """Translate a chunk of text, verifying the output. Returns the translated string."""
        if stop_flag and stop_flag(): return "[[TRANSLATION_STOPPED]]" 
        if not chunk or not chunk.strip(): return ""
        if len(chunk) > self.max_input_length: chunk = chunk[:self.max_input_length]

        with self.processing_lock:
            for attempt in range(self.retry_attempts):

                if stop_flag and stop_flag():
                    self.logger.info("Stop signal detected during retry loop. Halting translation.")
                    return "[[TRANSLATION_STOPPED]]"

                try:
                    self.logger.info(f"Translating chunk (length: {len(chunk)}). Attempt {attempt + 1}/{self.retry_attempts}")

                    if not self.ensure_login(): raise Exception("Login failed.")

                    self._dismiss_overlays_and_popups() 

                    elapsed = time.time() - self.last_used_time
                    if elapsed < self.cooldown:

                        remaining_sleep = self.cooldown - elapsed
                        sleep_end_time = time.time() + remaining_sleep
                        while time.time() < sleep_end_time:
                            if stop_flag and stop_flag():
                                self.logger.info("Stop signal detected during cooldown. Halting translation.")
                                return "[[TRANSLATION_STOPPED]]"
                            time.sleep(0.1) 

                    input_element = self.find_input_element()
                    if not input_element: raise Exception("Could not find source text input.")

                    self.driver.execute_script("arguments[0].innerHTML = ''", input_element)

                    if not self.set_input_text(input_element, chunk): raise Exception("Failed to set text.")

                    self.last_used_time = time.time()

                    translated_text = self.wait_for_response(len(chunk), stop_flag=stop_flag)

                    if translated_text == "[[TRANSLATION_STOPPED]]":
                        return "[[TRANSLATION_STOPPED]]"

                    if translated_text and translated_text.strip():
                        try:
                            self.driver.execute_script("arguments[0].innerHTML = ''", input_element)
                            self.logger.debug("Cleared source input after successful translation.")
                        except Exception:
                            self.logger.warning("Could not clear source input after translation.")
                        return translated_text
                    else:
                        raise Exception("Received an empty or invalid translation.")
                except InterruptedError:

                    self.logger.info("Translation process gracefully interrupted by user signal.")
                    return "[[TRANSLATION_STOPPED]]"
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if "usage limit" in str(e).lower():

                        messagebox.showerror("DeepL Limit Reached", "You have hit the DeepL free usage limit.")
                        return f"[[TRANSLATION FAILED: USAGE LIMIT REACHED]]"

                    if attempt < self.retry_attempts - 1:
                        self.logger.info("Retrying after a delay by refreshing page.")
                        self.human_delay(3, 5) 
                        self.driver.refresh()
                        self.is_logged_in = False
                    else:
                        self.logger.error("All translation attempts failed for this chunk.")
                        return f"[[TRANSLATION FAILED: {chunk[:50]}...]]"

            return f"[[TRANSLATION FAILED: {chunk[:50]}...]]"