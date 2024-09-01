import json
import os
import time
from multiprocessing import Pool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException
from bs4 import BeautifulSoup

def login_and_extract_data(credentials):
    email, password = credentials
    chrome_driver_path = r"/home/ravneet/.wdm/drivers/chromedriver/linux64/127.0.6533.119/chromedriver"  # Update this path
    service = Service(chrome_driver_path)

    chrome_options = Options()
    #chrome_options.add_argument("-headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=0")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get("https://admin.shopify.com/store")
        print(f"[{email}] Navigated to: {driver.current_url}")

        # Login process
        email_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "account_email"))
        )
        email_field.send_keys(email)
        print(f"[{email}] Entered email")

        next_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.NAME, "commit"))
        )
        next_button.click()
        print(f"[{email}] Clicked 'Next' button")

        WebDriverWait(driver, 30).until(
            EC.url_contains("lookup")
        )
        print(f"[{email}] Current URL: {driver.current_url}")

        password_field = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "account_password"))
        )
        password_field.send_keys(password)
        print(f"[{email}] Entered password")

        login_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.NAME, "commit"))
        )
        login_button.click()
        print(f"[{email}] Clicked login button")

        # Wait for successful login and Orders link to be present
        orders_link = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.Polaris-Navigation__Item[href*='/orders']"))
        )
        print(f"[{email}] Login successful!")

        # Click on the Orders link
        orders_link.click()
        print(f"[{email}] Clicked on Orders link")

        # Wait for the orders page to load
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr[id^='gid://shopify/Order/']"))
        )
        print(f"[{email}] Orders page loaded successfully")

        # Create 'data' folder if it doesn't exist
        if not os.path.exists('data'):
            os.makedirs('data')

        # Extract order data
        order_rows = driver.find_elements(By.CSS_SELECTOR, 'tr[id^="gid://shopify/Order/"]')

        for i in range(len(order_rows)):
            try:
                # Re-fetch the order rows to avoid stale element reference
                order_rows = driver.find_elements(By.CSS_SELECTOR, 'tr[id^="gid://shopify/Order/"]')
                order_row = order_rows[i]

                # Locate the link to the order details page
                order_link = order_row.find_element(By.CSS_SELECTOR, 'td:nth-child(2) a')
                order_id = order_row.get_attribute('id').split('/')[-1]
                
                # Click the order link using JavaScript
                driver.execute_script("arguments[0].click();", order_link)
                print(f"[{email}] Clicked on order {order_id}")
                
                # Retry mechanism
                for attempt in range(3):
                    try:
                        # Wait for the order details page to load
                        WebDriverWait(driver, 60).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div._OrderDetailsSidebar_151vv_192"))
                        )
                        print(f"[{email}] Order details page loaded for {order_id}")

                        # Extract order details from the new page
                        html_content = driver.page_source
                        soup = BeautifulSoup(html_content, 'html.parser')

                        # Extract customer name
                        customer_name_elem = soup.select_one('div[aria-label="Customer"] a.Polaris-Link')
                        customer_name = customer_name_elem.text.strip() if customer_name_elem else "N/A"
                        print(f"[{email}] Customer name: {customer_name}")

                        # Extract customer email
                        customer_email_elem = soup.select_one('div._EmailSection_1mru8_12 button.Polaris-Link')
                        customer_email = customer_email_elem.text.strip() if customer_email_elem else "N/A"
                        print(f"[{email}] Customer email: {customer_email}")

                        # Extract phone number
                        phone_number_elem = soup.select_one('a[href^="tel:"]')
                        phone_number = phone_number_elem.text.strip() if phone_number_elem else "No phone number"
                        print(f"[{email}] Phone number: {phone_number}")

                        # Extract shipping address
                        shipping_address_elem = soup.select_one('div._addressWrapper_1ljlz_5 p')
                        shipping_address = shipping_address_elem.text.strip() if shipping_address_elem else "N/A"
                        print(f"[{email}] Shipping address: {shipping_address}")

                        # Check if billing address is the same as shipping address
                        billing_address_same_elem = soup.select_one('div.Polaris-Text--bodyMd.Polaris-Text--subdued')
                        billing_address_same = billing_address_same_elem.text.strip() if billing_address_same_elem else "N/A"
                        print(f"[{email}] Billing address info: {billing_address_same}")

                        order_data = {
                            'order_id': order_id,
                            'customer_name': customer_name,
                            'customer_email': customer_email,
                            'phone_number': phone_number,
                            'shipping_address': shipping_address,
                            'billing_address_same': billing_address_same
                        }

                        with open(f'data/order_{order_id}_{email}.json', 'w') as f:
                            json.dump(order_data, f, indent=4)
                        print(f"[{email}] Data saved to data/order_{order_id}_{email}.json")
                        
                        break 
                    except TimeoutException:
                        print(f"[{email}] Timeout occurred while loading order {order_id}. Retrying... (Attempt {attempt + 1}/3)")
                        time.sleep(2) 
                        driver.refresh()  

                # Navigate back to the main orders page
                driver.back()
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[id^="gid://shopify/Order/"]'))
                )
                print(f"[{email}] Returned to the orders list")

            except StaleElementReferenceException as e:
                print(f"[{email}] Stale element reference encountered for order {order_id}. Refetching the element.")
                print(str(e))
                continue  

            except Exception as e:
                print(f"[{email}] Unexpected error occurred while processing order {order_id}: {str(e)}")
                continue  

        print(f"[{email}] Extracted data for {len(order_rows)} orders")

    except TimeoutException as e:
        print(f"[{email}] Timeout occurred. The page or element didn't load in time.")
        print(str(e))
    except NoSuchElementException as e:
        print(f"[{email}] An element was not found on the page.")
        print(str(e))
    except ElementNotInteractableException as e:
        print(f"[{email}] An element was found but could not be interacted with.")
        print(str(e))
    except Exception as e:
        print(f"[{email}] An unexpected error occurred: {str(e)}")
    finally:
        print(f"[{email}] Final URL: {driver.current_url}")
        driver.quit()

def stress_test(accounts):
    with Pool(processes=len(accounts)) as pool:
        pool.map(login_and_extract_data, accounts)

if __name__ == "__main__":
    accounts = [
        ("mk7863521@gmail.com", "Shopify645"),
        ("isotineplus1197@gmail.com", "Shopify664"),
        ("kuldeepchaurasia942@gmail.com", "Shopify994"),
        ("manikantpandey6@gmail.com", "Shopify119"),
        ("marpan937@gmail.com", "Shopify898")
    ]
    stress_test(accounts)
