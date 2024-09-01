import json
import os
import time
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException
from bs4 import BeautifulSoup
from webdriver_manager.firefox import GeckoDriverManager

def wait_and_click(driver, by, value, timeout=30):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(2)  # Increased delay to ensure the element is in view and page is settled
    driver.execute_script("arguments[0].click();", element)

def login_and_extract_data(email, password):
    firefox_options = Options()
    firefox_options.add_argument("-headless")  # Uncomment this line to run in headless mode
    firefox_options.add_argument("--width=1920")
    firefox_options.add_argument("--height=1080")

    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=firefox_options)

    try:
        driver.get("https://accounts.shopify.com/login")
        print(f"Navigated to: {driver.current_url}")

        # Login process
        email_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "account_email"))
        )
        email_field.send_keys(email)
        print("Entered email")

        wait_and_click(driver, By.NAME, "commit")
        print("Clicked 'Next' button")

        # Wait for password field
        password_field = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "account_password"))
        )
        driver.execute_script("arguments[0].value = arguments[1]", password_field, password)
        print("Entered password")

        wait_and_click(driver, By.NAME, "commit")
        print("Clicked login button")

        # Wait for successful login and navigation to admin page
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr[id^='gid://shopify/Order/']"))
        )
        print("Login successful!")

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

                order_id = order_row.get_attribute('id').split('/')[-1]
                
                # Click the order link using our custom function
                wait_and_click(driver, By.CSS_SELECTOR, f'tr[id$="{order_id}"] td:nth-child(2) a')
                print(f"Clicked on order {order_id}")
                
                # Wait for the order details page to load
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div._OrderDetailsSidebar_151vv_192"))
                )
                print(f"Order details page loaded for {order_id}")

                # Extract order details from the new page
                html_content = driver.page_source
                soup = BeautifulSoup(html_content, 'html.parser')

                # Extract customer name
                customer_name_elem = soup.select_one('div[aria-label="Customer"] a.Polaris-Link')
                customer_name = customer_name_elem.text.strip() if customer_name_elem else "N/A"
                print(f"Customer name: {customer_name}")

                # Extract customer email
                customer_email_elem = soup.select_one('div._EmailSection_1mru8_12 button.Polaris-Link')
                customer_email = customer_email_elem.text.strip() if customer_email_elem else "N/A"
                print(f"Customer email: {customer_email}")

                # Extract phone number
                phone_number_elem = soup.select_one('a[href^="tel:"]')
                phone_number = phone_number_elem.text.strip() if phone_number_elem else "No phone number"
                print(f"Phone number: {phone_number}")

                # Extract shipping address
                shipping_address_elem = soup.select_one('div._addressWrapper_1ljlz_5 p')
                shipping_address = shipping_address_elem.text.strip() if shipping_address_elem else "N/A"
                print(f"Shipping address: {shipping_address}")

                # Check if billing address is the same as shipping address
                billing_address_same_elem = soup.select_one('div.Polaris-Text--bodyMd.Polaris-Text--subdued')
                billing_address_same = billing_address_same_elem.text.strip() if billing_address_same_elem else "N/A"
                print(f"Billing address info: {billing_address_same}")

                order_data = {
                    'order_id': order_id,
                    'customer_name': customer_name,
                    'customer_email': customer_email,
                    'phone_number': phone_number,
                    'shipping_address': shipping_address,
                    'billing_address_same': billing_address_same
                }

                with open(f'data/order_{order_id}.json', 'w') as f:
                    json.dump(order_data, f, indent=4)
                print(f"Data saved to data/order_{order_id}.json")

                # Navigate back to the main orders page
                driver.back()
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[id^="gid://shopify/Order/"]'))
                )
                print(f"Returned to the orders list")

            except StaleElementReferenceException:
                print(f"Stale element reference encountered for order {order_id}. Refetching the element.")
                continue

            except Exception as e:
                print(f"Unexpected error occurred while processing order {order_id}: {str(e)}")
                continue

        print(f"Extracted data for {len(order_rows)} orders")

    except TimeoutException as e:
        print("Timeout occurred. The page or element didn't load in time.")
        print(str(e))
    except NoSuchElementException as e:
        print("An element was not found on the page.")
        print(str(e))
    except ElementNotInteractableException as e:
        print("An element was found but could not be interacted with.")
        print(str(e))
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    finally:
        print(f"Final URL: {driver.current_url}")
        driver.quit()

if __name__ == "__main__":
    email = "marpan937@gmail.com"  # Replace with your Shopify account email
    password = "Shopify898"  # Replace with your Shopify account password
    login_and_extract_data(email, password)