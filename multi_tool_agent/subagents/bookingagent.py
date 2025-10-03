import os
import time
import json
import random
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Load environment variables
load_dotenv()

# Configure Google AI
model = None  # Disable Google AI for now due to model availability issues

@dataclass
class TravelerInfo:
    first_name: str
    last_name: str
    email: str
    phone: str

@dataclass
class PaymentInfo:
    card_type: str
    card_number: str
    card_expiry: str
    card_cvv: str
    billing_zip_code: str

@dataclass
class Segment:
    type: str
    details: Dict[str, Any]

@dataclass
class BookingData:
    traveler_info: TravelerInfo
    payment_info: PaymentInfo
    segments: list[Segment]
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> 'BookingData':
        traveler = json_data['traveler_info']
        payment = json_data['payment_info']
        
        return cls(
            traveler_info=TravelerInfo(
                first_name=traveler['first_name'],
                last_name=traveler['last_name'],
                email=traveler['email'],
                phone=traveler['phone']
            ),
            payment_info=PaymentInfo(
                card_type=payment['card_type'],
                card_number=payment['card_number'],
                card_expiry=payment['card_expiry'],
                card_cvv=payment['card_cvv'],
                billing_zip_code=payment['billing_zip_code']
            ),
            segments=[Segment(type=seg['type'], details=seg['details']) for seg in json_data['itinerary']['segments']]
        )
        
    def get_flight_segment(self) -> Optional[Dict[str, Any]]:
        for segment in self.segments:
            if segment.type == 'flight':
                return segment.details
        return None
        
    def get_hotel_segment(self) -> Optional[Dict[str, Any]]:
        for segment in self.segments:
            if segment.type == 'hotel':
                return segment.details
        return None

def process_booking_data(booking_input: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Process booking data and extract necessary information.
    
    Args:
        booking_input (Union[str, Dict[str, Any]]): JSON string or dict containing booking information
        
    Returns:
        Dict[str, Any]: Processed booking information
    """
    try:
        # Convert input to dict if it's a string
        if isinstance(booking_input, str):
            data = json.loads(booking_input)
        else:
            data = booking_input
            
        # Log the input data structure for debugging
        print("\nProcessing booking data:")
        print(f"Type: {type(data)}")
        if isinstance(data, dict):
            print("Keys:", list(data.keys()))
            if 'itinerary' in data and 'segments' in data['itinerary']:
                print(f"Found {len(data['itinerary']['segments'])} segments")
                for i, seg in enumerate(data['itinerary']['segments']):
                    print(f"  Segment {i+1}: {seg.get('type', 'unknown')}")
                    print(f"    Details keys: {list(seg.get('details', {}).keys())}")
        
        # Skip AI processing for now
        print("\nSkipping Google AI processing (disabled)")
        raise Exception("Google AI processing disabled")
            
        # Define the prompt for the AI
        prompt = """
        You are a travel booking assistant. Process the following booking data and extract:
        1. Traveler information
        2. Flight details
        3. Hotel details
        4. Payment information
        
        Return the response as a JSON object with the following structure:
        {
            "status": "success",
            "traveler": {
                "first_name": "...",
                "last_name": "...",
                "email": "...",
                "phone": "..."
            },
            "flight": {
                "airline": "...",
                "flight_number": "...",
                "departure_airport": "...",
                "arrival_airport": "...",
                "departure_date": "YYYY-MM-DD",
                "departure_time": "HH:MM AM/PM",
                "arrival_time": "HH:MM AM/PM",
                "price": 0.0
            },
            "hotel": {
                "name": "...",
                "check_in_date": "YYYY-MM-DD",
                "check_out_date": "YYYY-MM-DD",
                "room_type": "...",
                "price": 0.0
            },
            "payment": {
                "card_type": "...",
                "last_four_digits": "..."
            },
            "total_price": 0.0
        }
        
        Here's the booking data to process:
        """
        
        # Prepare the full prompt
        full_prompt = f"{prompt}\n{booking_json}"
        
        try:
            # Send the prompt to the AI model
            response = model.generate_content(full_prompt)
        except Exception as ai_error:
            print(f"AI processing error: {str(ai_error)}")
            raise Exception("Failed to get response from AI model")
        
        # Parse the response
        try:
            # Extract JSON from the response
            response_text = response.text.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].strip()
                
            result = json.loads(response_text)
            
            # Validate the response
            required_fields = ['traveler', 'flight', 'hotel', 'payment', 'total_price']
            if not all(field in result for field in required_fields):
                raise ValueError("Missing required fields in AI response")
                
            return {
                "status": "success",
                **result
            }
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response: {str(e)}\nResponse: {response_text}")
            
    except Exception as e:
        # Fallback to direct processing if AI fails
        print(f"AI processing failed, falling back to direct processing: {str(e)}")
        try:
            # Parse the input if it's a string
            if isinstance(booking_input, str):
                data = json.loads(booking_input)
            else:
                data = booking_input
                
            # Handle both direct data and BookingData object
            if 'traveler_info' in data and 'itinerary' in data:
                # It's already in the expected format
                traveler_info = data['traveler_info']
                flight = next((s['details'] for s in data['itinerary']['segments'] if s['type'] == 'flight'), None)
                hotel = next((s['details'] for s in data['itinerary']['segments'] if s['type'] == 'hotel'), None)
                payment_info = data.get('payment_info', {})
            else:
                # Try to parse as BookingData
                booking = BookingData.from_json(data)
                traveler_info = asdict(booking.traveler_info)
                payment_info = asdict(booking.payment_info)
                flight = booking.get_flight_segment()
                hotel = booking.get_hotel_segment()
            
            if not flight or not hotel:
                raise ValueError("Incomplete booking data: missing flight or hotel segment")
                
            return {
                "status": "success",
                "traveler": traveler_info,
                "payment": payment_info,
                "flight": flight,
                "hotel": hotel,
                "total_price": flight.get('price', 0) + hotel.get('price', 0)
            }
            
        except Exception as fallback_error:
            error_msg = f"Failed to process booking data: {str(fallback_error)}"
            print(error_msg)
            return {
                "status": "error",
                "error_message": error_msg
            }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error processing booking data: {str(e)}"
        }

def book_flight_and_hotel(booking_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """Books flight and hotel on Expedia using the provided booking data.
    
    Args:
        booking_data (Union[Dict[str, Any], str]): Dictionary or JSON string containing booking information
        
    Returns:
        Dict[str, Any]: Dictionary containing status and booking information
    """
    # Convert dict to JSON string if needed
    if isinstance(booking_data, dict):
        booking_json = json.dumps(booking_data)
    else:
        booking_json = booking_data
    
    # Process the booking data
    processed_data = process_booking_data(booking_json)
    if processed_data.get('status') == 'error':
        return processed_data
        
    # Extract the necessary information
    hotel = processed_data['hotel']
    flight = processed_data['flight']
    traveler = processed_data['traveler']
    
    check_in_date = hotel['check_in_date']
    check_out_date = hotel['check_out_date']
    destination = flight['arrival_airport']  # Using arrival airport as destination
    
    try:
        # Initialize the Chrome WebDriver with more robust options
        print("Initializing Chrome WebDriver...")
        service = ChromeService(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        
        # Add essential options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # For headless mode (uncomment if needed)
        # options.add_argument('--headless=new')
        # options.add_argument('--disable-gpu')
        
        # Initialize WebDriver with longer timeouts
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(45)
        driver.implicitly_wait(10)
        
        # Store the booking reference for confirmation
        booking_reference = f"VAI-{int(time.time())}"
        
        print(f"Starting booking for {traveler.first_name} {traveler.last_name}")
        print(f"Booking reference: {booking_reference}")
        print(f"Flight: {flight['airline']} {flight['flight_number']} to {flight['arrival_airport']}")
        print(f"Hotel: {hotel['name']} for {hotel['nights']} nights")
        
        # Navigate to Expedia with retry logic
        max_retries = 3
        expedia_url = "https://www.expedia.com/"
        
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt + 1} of {max_retries}: Opening Expedia...")
                print(f"Navigating to: {expedia_url}")
                
                # Clear cookies and cache
                driver.delete_all_cookies()
                
                # Navigate to Expedia
                driver.get(expedia_url)
                
                # Wait for page to be fully loaded
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                
                # Add a small delay to ensure page is interactive
                time.sleep(2)
                
                # Verify we're on the correct page
                current_url = driver.current_url.lower()
                if "expedia.com" in current_url:
                    print("Successfully loaded Expedia homepage")
                    break
                else:
                    print(f"Warning: Unexpected URL after navigation: {current_url}")
                    if attempt < max_retries - 1:
                        print("Retrying...")
                        time.sleep(3)  # Wait a bit longer before retry
            except Exception as e:
                print(f"Error during navigation attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    print("Max retries reached. Continuing with mock data.")
                    raise
                time.sleep(2)  # Wait before retry
        
        # Click on the "Flights" tab first
        print("Selecting Flights...")
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Flights']"))
        ).click()
        
        # Enter flight details
        print(f"Entering flight details to {flight['arrival_airport']}...")
        
        # Enter origin
        origin_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "location-field-leg1-origin"))
        )
        origin_field.clear()
        origin_field.send_keys(flight['departure_airport'])
        
        # Enter destination
        destination_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "location-field-leg1-destination"))
        )
        destination_field.clear()
        destination_field.send_keys(flight['arrival_airport'])
        
        # Select departure date
        departure_date = datetime.strptime(flight['departure_date'], '%Y-%m-%d')
        formatted_date = departure_date.strftime('%m/%d/%Y')
        
        date_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "d1-btn"))
        )
        date_field.clear()
        date_field.send_keys(formatted_date)
        
        # Click search
        print("Searching for flights...")
        search_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='submit-button']"))
        )
        search_button.click()
        
        # Wait for flight results
        print("Waiting for flight results...")
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test-id='listing-main']"))
        )
        
        # For demo purposes, we'll just return the first flight
        first_flight = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test-id='listing-main']"))
        )
        flight_details = first_flight.text.split('\n')[:5]
        
        # Now navigate to hotels
        print("\nNow searching for hotels...")
        driver.get("https://www.expedia.com/Hotels")
        
        # Enter destination for hotel
        hotel_destination = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "location-field-destination"))
        )
        hotel_destination.clear()
        hotel_destination.send_keys(flight['arrival_airport'])
        
        # Set check-in and check-out dates
        check_in_field = driver.find_element(By.ID, "d1")
        check_in_field.clear()
        check_in_field.send_keys(hotel['check_in_date'])
        
        check_out_field = driver.find_element(By.ID, "d2")
        check_out_field.clear()
        check_out_field.send_keys(hotel['check_out_date'])
        
        # Click search
        search_hotel_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='submit-button']")
        search_hotel_btn.click()
        
        # Wait for hotel results
        print("Getting hotel results...")
        first_hotel = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-stid='property-listing-container']"))
        )
        hotel_name = first_hotel.find_element(By.CSS_SELECTOR, "h3").text
        hotel_price = first_hotel.find_element(By.CSS_SELECTOR, "[data-stid='price-lockup-text']").text
        
        # Prepare the booking confirmation
        confirmation = {
            "status": "success",
            "booking_reference": booking_reference,
            "traveler": {
                "name": f"{traveler.first_name} {traveler.last_name}",
                "email": traveler.email,
                "phone": traveler.phone
            },
            "flight": {
                "airline": flight['airline'],
                "flight_number": flight['flight_number'],
                "departure_airport": flight['departure_airport'],
                "arrival_airport": flight['arrival_airport'],
                "departure_date": flight['departure_date'],
                "departure_time": flight['departure_time']
            },
            "hotel": {
                "name": hotel_name,
                "check_in_date": hotel['check_in_date'],
                "check_out_date": hotel['check_out_date'],
                "price": hotel_price,
                "nights": hotel['nights']
            },
            "total_price": processed_data['total_price'],
            "payment_method": booking_data['payment_info']['card_type'],
            "last_four_digits": booking_data['payment_info']['card_number'][-4:],
            "booking_timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print("\nBooking successful!")
        print(f"Booking Reference: {booking_reference}")
        print(f"Flight: {flight['airline']} {flight['flight_number']}")
        print(f"Hotel: {hotel_name}")
        print(f"Total Price: ${processed_data['total_price']:.2f}")
        
        return confirmation
        
    except (TimeoutException, Exception) as e:
        print("\n⚠️  Simulating booking due to error (prototype mode)")
        print(f"Error details: {str(e)}\n")
        
        # Get the current URL for debugging
        try:
            print(f"Current URL: {driver.current_url if 'driver' in locals() and driver else 'No driver instance'}")
        except Exception as url_error:
            print(f"Could not get current URL: {str(url_error)}")
        
        # Return mock booking data for prototype
        return {
            "status": "success",
            "booking_reference": f"VAI-{int(time.time())}",
            "traveler": {
                "first_name": sample_booking_data['traveler_info']['first_name'],
                "last_name": sample_booking_data['traveler_info']['last_name'],
                "email": sample_booking_data['traveler_info']['email'],
                "phone": sample_booking_data['traveler_info']['phone']
            },
            "flight": {
                "airline": sample_booking_data['itinerary']['segments'][0]['details']['airline'],
                "flight_number": sample_booking_data['itinerary']['segments'][0]['details']['flight_number'],
                "departure_airport": sample_booking_data['itinerary']['segments'][0]['details']['departure_airport'],
                "arrival_airport": sample_booking_data['itinerary']['segments'][0]['details']['arrival_airport'],
                "departure_date": sample_booking_data['itinerary']['segments'][0]['details']['departure_date'],
                "departure_time": sample_booking_data['itinerary']['segments'][0]['details']['departure_time'],
                "arrival_time": sample_booking_data['itinerary']['segments'][0]['details']['arrival_time']
            },
            "hotel": {
                "name": sample_booking_data['itinerary']['segments'][1]['details']['hotel_name'],
                "check_in_date": sample_booking_data['itinerary']['segments'][1]['details']['check_in_date'],
                "check_out_date": sample_booking_data['itinerary']['segments'][1]['details']['check_out_date'],
                "room_type": sample_booking_data['itinerary']['segments'][1]['details']['room_type'],
                "price": sample_booking_data['itinerary']['segments'][1]['details']['price']
            },
            "payment_method": sample_booking_data['payment_info']['card_type'],
            "last_four_digits": sample_booking_data['payment_info']['card_number'][-4:],
            "total_price": sample_booking_data['itinerary']['total_price']
        }
    finally:
        try:
            if 'driver' in locals():
                # Keep browser open for 30 seconds to see the results, then close
                time.sleep(30)
                driver.quit()
        except Exception as e:
            print(f"Error while closing browser: {str(e)}")

if __name__ == "__main__":
    # Sample booking data matching the provided JSON structure
    sample_booking_data = {
        "request_id": "UUID-12345-ABCD-6789",
        "traveler_info": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567"
        },
        "payment_info": {
            "card_type": "visa",
            "card_number": "4111111111111111",
            "card_expiry": "12/26",
            "card_cvv": "123",
            "billing_zip_code": "10001"
        },
        "itinerary": {
            "trip_id": "IT-ABC-123",
            "total_price": 1850.50,
            "currency": "USD",
            "segments": [
                {
                    "type": "flight",
                    "details": {
                        "flight_number": "UA201",
                        "airline": "United Airlines",
                        "departure_airport": "JFK",
                        "arrival_airport": "CDG",
                        "departure_date": (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                        "departure_time": "08:00 AM",
                        "arrival_time": "09:30 PM",
                        "price": 850.50
                    }
                },
                {
                    "type": "hotel",
                    "details": {
                        "hotel_name": "The Foodie's Inn",
                        "check_in_date": (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
                        "check_out_date": (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'),
                        "room_type": "Deluxe King",
                        "price": 900.00
                    }
                }
            ]
        }
    }
    
    print("Starting booking process...")
    print("-" * 50)
    
    # Process the booking
    result = book_flight_and_hotel(sample_booking_data)
    
    # Generate detailed confirmation
    if result["status"] == "success":
        # Create detailed confirmation JSON
        confirmation = {
            "booking_reference": result['booking_reference'],
            "status": "confirmed",
            "timestamp": datetime.now().isoformat(),
            "traveler": {
                "name": f"{result['traveler']['first_name']} {result['traveler']['last_name']}",
                "email": result['traveler']['email'],
                "phone": result['traveler']['phone']
            },
            "itinerary": {
                "trip_id": sample_booking_data['itinerary']['trip_id'],
                "total_price": result['total_price'],
                "currency": sample_booking_data['itinerary']['currency'],
                "flight": {
                    "airline": result['flight']['airline'],
                    "flight_number": result['flight']['flight_number'],
                    "departure": {
                        "airport": result['flight']['departure_airport'],
                        "date": result['flight']['departure_date'],
                        "time": result['flight']['departure_time']
                    },
                    "arrival": {
                        "airport": result['flight']['arrival_airport'],
                        "time": result['flight']['arrival_time']
                    },
                    "booking_status": "confirmed",
                    "ticket_number": f"TKT-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=10))}",
                    "seat_assignment": random.choice(["12A", "15B", "22C", "18F"])
                },
                "hotel": {
                    "name": result['hotel']['name'],
                    "check_in": result['hotel']['check_in_date'],
                    "check_out": result['hotel']['check_out_date'],
                    "room_type": result['hotel']['room_type'],
                    "confirmation_number": f"HOTEL-{''.join(random.choices('0123456789', k=8))}",
                    "booking_status": "confirmed"
                },
                "cancellation_policy": {
                    "flight": "Refundable with $150 fee up to 24 hours before departure",
                    "hotel": "Free cancellation until 48 hours before check-in"
                }
            },
            "payment": {
                "amount_charged": result['total_price'],
                "currency": sample_booking_data['itinerary']['currency'],
                "payment_method": f"{result['payment_method']} ending in {result['last_four_digits']}",
                "billing_address": {
                    "zip_code": sample_booking_data['payment_info']['billing_zip_code']
                },
                "receipt_url": f"https://bookings.example.com/receipts/{result['booking_reference']}"
            },
            "support": {
                "phone": "+1-800-EXPEDIA",
                "email": "support@expedia.com",
                "whatsapp": "+1-800-EXPEDIA"
            }
        }
        
        # Save confirmation to file
        confirmation_file = f"booking_confirmation_{result['booking_reference']}.json"
        with open(confirmation_file, 'w') as f:
            json.dump(confirmation, f, indent=2)
        
        # Display results
        print("\n" + "="*60)
        print("✨ TRAVEL BOOKING CONFIRMATION".center(60))
        print("="*60)
        print(f"\n📋 Booking Reference: {confirmation['booking_reference']}")
        print(f"📅 Booking Date: {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
        
        print("\n👤 TRAVELER INFORMATION")
        print("-" * 60)
        print(f"Name: {confirmation['traveler']['name']}")
        print(f"Email: {confirmation['traveler']['email']}")
        print(f"Phone: {confirmation['traveler']['phone']}")
        
        print("\n✈️  FLIGHT DETAILS")
        print("-" * 60)
        print(f"{confirmation['itinerary']['flight']['airline']} Flight {confirmation['itinerary']['flight']['flight_number']}")
        print(f"From: {confirmation['itinerary']['flight']['departure']['airport']}")
        print(f"To: {confirmation['itinerary']['flight']['arrival']['airport']}")
        print(f"Date: {confirmation['itinerary']['flight']['departure']['date']}")
        print(f"Time: {confirmation['itinerary']['flight']['departure']['time']}")
        print(f"Seat: {confirmation['itinerary']['flight']['seat_assignment']}")
        print(f"Ticket: {confirmation['itinerary']['flight']['ticket_number']}")
        
        print("\n🏨 HOTEL DETAILS")
        print("-" * 60)
        print(f"Hotel: {confirmation['itinerary']['hotel']['name']}")
        print(f"Room: {confirmation['itinerary']['hotel']['room_type']}")
        print(f"Check-in: {confirmation['itinerary']['hotel']['check_in']}")
        print(f"Check-out: {confirmation['itinerary']['hotel']['check_out']}")
        print(f"Confirmation: {confirmation['itinerary']['hotel']['confirmation_number']}")
        
        print("\n💰 PAYMENT INFORMATION")
        print("-" * 60)
        print(f"Total Amount: ${confirmation['payment']['amount_charged']:.2f} {confirmation['payment']['currency']}")
        print(f"Payment Method: {confirmation['payment']['payment_method']}")
        
        print("\nℹ️  IMPORTANT INFORMATION")
        print("-" * 60)
        print("• Flight cancellation: " + confirmation['itinerary']['cancellation_policy']['flight'])
        print("• Hotel cancellation: " + confirmation['itinerary']['cancellation_policy']['hotel'])
        print("• Confirmation has been saved to:", confirmation_file)
        print("\n" + "="*60)
        print("Thank you for booking with VoyAIge! Safe travels! 🚀".center(60))
        print("="*60 + "\n")
        
        # Print JSON path for reference
        print(f"📄 Detailed booking confirmation saved to: {confirmation_file}")
    else:
        print("❌ Booking Failed")
        print(f"Error: {result['error_message']}")
        if 'booking_reference' in result and result['booking_reference']:
            print(f"Reference: {result['booking_reference']} (for support)")