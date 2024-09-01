import os
import logging
import json
import random
import string
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

logging.basicConfig(filename='google_form_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,             
    allow_methods=["*"],
    allow_headers=["*"],
)

class FormURL(BaseModel):
    url: str

class GoogleFormBot:
    def __init__(self, form_url):
        self.form_url = form_url
        self.driver = None
        self.questions = []
        self.current_checkbox_question = None

    def setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-popup-blocking')
        options.page_load_strategy = 'normal'

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.driver.set_page_load_timeout(30)

    def load_form(self):
        try:
            self.driver.get(self.form_url)
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "form"))
            )
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logging.info("Form page loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load the Google Form: {str(e)}")
            raise

    def extract_and_fill_form(self):
        try:
            page_number = 1
            while True:
                logging.info(f"Extracting and filling questions on page {page_number}")
                self.extract_and_fill_questions_on_current_page()
                
                if not self.go_to_next_page():
                    break
                
                page_number += 1
            
            logging.info(f"Extracted a total of {len(self.questions)} questions from the form.")
        except Exception as e:
            logging.error(f"An error occurred while extracting and filling questions: {str(e)}")

    def go_to_next_page(self):
        try:
            next_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/ancestor::div[@role='button']"))
            )
            self.click_element_safely(next_button)
            WebDriverWait(self.driver, 10).until(
                EC.staleness_of(next_button)
            )
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            return True
        except (NoSuchElementException, TimeoutException):
            logging.info("No more pages found.")
            return False

    def extract_and_fill_questions_on_current_page(self):
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            question_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
            logging.info(f"Found {len(question_elements)} question elements on current page")
            
            for element in question_elements:
                max_retries = 3
                for _ in range(max_retries):
                    try:
                        question_text = self.extract_question_text(element)
                        question_type, options = self.determine_question_type(element)
                        
                        question_text = question_text.split('\n')[0]
                        
                        if question_type == "Section Header":
                            self.questions.append({
                                "type": "Section Header",
                                "text": question_text
                            })
                        elif question_type == "Checkboxes":
                            if self.current_checkbox_question is None:
                                self.current_checkbox_question = {
                                    "question": question_text,
                                    "type": "Checkboxes",
                                    "options": []
                                }
                                self.questions.append(self.current_checkbox_question)
                            else:
                                self.current_checkbox_question["options"].append(question_text)
                        else:
                            if self.current_checkbox_question:
                                self.current_checkbox_question = None
                            question_data = {
                                "question": question_text,
                                "type": question_type
                            }
                            if options:
                                question_data["options"] = options
                            self.questions.append(question_data)
                        
                        if question_type != "Section Header":
                            self.fill_question(element, question_type, options)
                        break
                    except StaleElementReferenceException:
                        logging.warning("Stale element encountered, retrying.")
                        self.driver.refresh()
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[role='listitem']"))
                        )
                else:
                    logging.warning("Failed to extract and fill question after multiple attempts.")
        except Exception as e:
            logging.error(f"Error extracting and filling questions on current page: {str(e)}")

    def extract_question_text(self, element):
        try:
            question_text_element = element.find_element(By.CSS_SELECTOR, 
                ".freebirdFormviewerComponentsQuestionBaseTitle, .freebirdFormviewerComponentsQuestionBaseHeader, .freebirdFormviewerComponentsQuestionText")
            question_text = question_text_element.text
        except NoSuchElementException:
            question_text = element.text
        
        return question_text

    def determine_question_type(self, question_element):
        question_text = self.extract_question_text(question_element)
        all_options = [opt.strip() for opt in question_text.split('\n') if opt.strip()]
        options = [opt for opt in all_options[1:] if opt != '*']

        if question_element.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='date']"):
            return "Short Answer", []
        elif question_element.find_elements(By.CSS_SELECTOR, "textarea"):
            return "Paragraph", []
        elif question_element.find_elements(By.CSS_SELECTOR, "label[role='radio'], div[role='radio']"):
            return "Radio_Button", options
        elif question_element.find_elements(By.CSS_SELECTOR, "label[role='checkbox'], div[role='checkbox']"):
            return "Checkboxes", options
        elif question_element.find_elements(By.CSS_SELECTOR, "div[role='listbox']"):
            return "Dropdown", options
        elif question_element.find_elements(By.CSS_SELECTOR, ".OxAavc"):
            return "Section Header", []
        else:
            logging.warning(f"Unknown question type. Element HTML: {question_element.get_attribute('outerHTML')}")
            return "Unknown", options

    def fill_question(self, element, question_type, options):
        if question_type == "Short Answer":
            input_element = element.find_element(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='date']")
            self.send_keys_safely(input_element, self.generate_random_string())
        elif question_type == "Paragraph":
            textarea_element = element.find_element(By.CSS_SELECTOR, "textarea")
            self.send_keys_safely(textarea_element, self.generate_random_paragraph())
        elif question_type == "Radio_Button":
            radio_options = element.find_elements(By.CSS_SELECTOR, "label[role='radio'], div[role='radio']")
            non_other_options = [opt for opt in radio_options if "Other" not in opt.text]
            if non_other_options:
                self.click_element_safely(random.choice(non_other_options))
        elif question_type == "Checkboxes":
            checkbox_options = element.find_elements(By.CSS_SELECTOR, "label[role='checkbox'], div[role='checkbox']")
            non_other_options = [opt for opt in checkbox_options if "Other" not in opt.text]
            num_to_select = min(2, len(non_other_options))
            for checkbox in random.sample(non_other_options, num_to_select):
                self.click_element_safely(checkbox)
        elif question_type == "Dropdown":
            dropdown = element.find_element(By.CSS_SELECTOR, "div[role='listbox']")
            self.click_element_safely(dropdown)
            options = self.driver.find_elements(By.CSS_SELECTOR, "div[role='option']")
            non_other_options = [opt for opt in options if "Other" not in opt.text]
            if non_other_options:
                self.click_element_safely(random.choice(non_other_options))

    def click_element_safely(self, element):
        try:
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
        except:
            self.driver.execute_script("arguments[0].click();", element)

    def send_keys_safely(self, element, text):
        try:
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(element))
            element.send_keys(text)
        except:
            self.driver.execute_script(f"arguments[0].value = '{text}';", element)

    def process_questions(self):
        processed_questions = []
        for question in self.questions:
            if question['type'] == 'Checkboxes':
                if 'options' in question:
                    question['options'] = [opt for opt in question['options'] if 'Other' not in opt]
                if question['options']:  # Only add if there are remaining options
                    processed_questions.append(question)
            elif 'Other' not in question.get('question', ''):
                if 'options' in question:
                    question['options'] = [opt for opt in question['options'] if 'Other' not in opt]
                processed_questions.append(question)
        self.questions = processed_questions

    def generate_random_string(self, length=10):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_random_paragraph(self, sentences=3):
        return ' '.join([self.generate_random_string(random.randint(5, 15)) + '.' for _ in range(sentences)])

    def save_to_json(self, filename="extracted_questions.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.questions, f, ensure_ascii=False, indent=2)
            logging.info(f"Saved extracted questions to {filename}")
        except Exception as e:
            logging.error(f"Error saving to JSON: {str(e)}")

    def run(self):
        try:
            self.setup_driver()
            self.load_form()
            self.extract_and_fill_form()
            self.process_questions()
            self.save_to_json()
        except Exception as e:
            logging.error(f"An error occurred during execution: {str(e)}")
            raise
        finally:
            if self.driver:
                self.driver.quit()

@app.post("/fetch_google_form")
async def fetch_google_form(form_url: FormURL):
    try:
        bot = GoogleFormBot(form_url.url)
        bot.run()
        return {"message": "Form filled and questions saved successfully", "questions": bot.questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_questions_and_options")
async def get_questions_and_options():
    try:
        with open("extracted_questions.json", "r") as f:
            questions = json.load(f)
        return {"questions": questions}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Questions not found. Please fetch a Google Form first.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding questions JSON.")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
    