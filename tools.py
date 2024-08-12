# This file is not maintained anymore. New way to adding custom tool is added now !!
import requests
from langchain.tools import tool, BaseTool, StructuredTool
from pydantic import BaseModel

tools_info = {
    "MeetingScheduler": {
        "name": "MeetingScheduler",
        "description": "Books meetings with clients."
    },
    "GymAppointmentAvailability": {
        "name": "GymAppointmentAvailability",
        "description": "Assistants must Check next appointment available in Gym and confirm with customer, before offering appointment to customer"
    },
    "OnsiteAppointment": {
        "name": "OnsiteAppointment",
        "description": "Book Onsite Gym Appointment as per user's availability."
    },
    "PriceInquiry": {
        "name": "PriceInquiry",
        "description": "Fetches product prices of Gym memberships.",
        "parameters": {
            "product_name": ["Silver-Gym-Membership", "Gold-Gym-Membership", "Platinum-Gym-Membership"]
        }
    }
}

#### Manual Tools/Method Implementation using Python functions ####

# def OnsiteAppointmentTool():
#     # Assume arguments is a dict that contains date and time
#     print('Onsite Appointment function is called')
#     return f"Onsite Appointment is booked."

# def FetchProductPriceTool(membership_type):
#     print('Fetch product price is called')

#     # Set up the endpoint and headers
#     url = 'https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip'
#     headers = {'Content-Type': 'application/json'}
    
#     # Prepare the data payload with the membership type
#     data = {
#         "membership": membership_type
#     }
    
#     # Send a POST request to the server
#     response = requests.post(url, headers=headers, json=data)
    
#     # Check if the request was successful
#     if response.status_code == 200:
#         # Parse the JSON response to get the price
#         price_info = response.json()
#         return f"The price is ${price_info['price']} per month."
#     else:
#         return "Failed to fetch the price, please try again later."

# def CalendlyMeetingTool():
#     print('Calendly Meeting invite is sent.')
#     # Assume arguments is a dict that contains date and time
#     return f"Calendly meeting invite is sent now."

# def AppointmentAvailabilityTool():
#     print('Checking appointment availability.')
#     # Assume arguments is a dict that contains date and time
#     return f"Our next available appointment is tomorrow, 24th April at 4 PM."

#### Define Langchain Tools/Method Implementation using tool decorator ####

# @tool
# def OnsiteAppointmentTool():
#     """
#     Book an onsite gym appointment.
#     """
#     print('Onsite Appointment function is called')
#     return f"Onsite Appointment is booked."

# @tool
# def FetchProductPriceTool(membership_type: str) -> str:
#     """
#     Fetch the price of a gym membership.

#     Args:
#         membership_type (str): The type of membership (e.g., Silver-Gym-Membership, Gold-Gym-Membership, Platinum-Gym-Membership).

#     Returns:
#         str: The price of the membership.
#     """
#     print('Fetch product price is called')

#     # Set up the endpoint and headers
#     url = 'https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip'
#     headers = {'Content-Type': 'application/json'}
    
#     # Prepare the data payload with the membership type
#     data = {
#         "membership": membership_type
#     }
    
#     # Send a POST request to the server
#     response = requests.post(url, headers=headers, json=data)
    
#     # Check if the request was successful
#     if response.status_code == 200:
#         # Parse the JSON response to get the price
#         price_info = response.json()
#         return f"The price is ${price_info['price']} per month."
#     else:
#         return "Failed to fetch the price, please try again later."

# @tool
# def CalendlyMeetingTool():
#     """
#     Send a Calendly meeting invite.
#     """
#     print('Calendly Meeting invite is sent.')
#     return f"Calendly meeting invite is sent now."

# @tool
# def AppointmentAvailabilityTool():
#     """
#     Check the next available appointment at the gym.
#     """
#     print('Checking appointment availability.')
#     return f"Our next available appointment is tomorrow, 24th April at 4 PM."


#### Define Langchain Tools/Method Implementation using Basetool Implementation for more flexibility and control. ####

class OnsiteAppointmentTool(BaseTool):
    name = "OnsiteAppointment"
    description = tools_info["OnsiteAppointment"]["description"]

    def _run(self) -> str:
        print('Onsite Appointment function is called')
        return f"Onsite Appointment is booked."




class FetchProductPriceTool(BaseTool):
    name = "PriceInquiry"
    description = tools_info["PriceInquiry"]["description"]

    def _run(self, membership_type: str) -> str:
        print('Fetch product price is called')

        # Set up the endpoint and headers
        url = 'https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip'
        headers = {'Content-Type': 'application/json'}
        
        # Prepare the data payload with the membership type
        data = {
            "membership": membership_type
        }
        
        # Send a POST request to the server
        response = requests.post(url, headers=headers, json=data)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response to get the price
            price_info = response.json()
            return f"The price is ${price_info['price']} per month."
        else:
            return "Failed to fetch the price, please try again later."

class CalendlyMeetingTool(BaseTool):
    name = "MeetingScheduler"
    description = tools_info["MeetingScheduler"]["description"]

    def _run(self) -> str:
        print('Calendly Meeting invite is sent.')
        return f"Calendly meeting invite is sent now."

class AppointmentAvailabilityTool(BaseTool):
    name = "GymAppointmentAvailability"
    description = tools_info["GymAppointmentAvailability"]["description"]

    def _run(self) -> str:
        print('Checking appointment availability.')
        return f"Our next available appointment is tomorrow, 24th April at 4 PM."
    

#### Define Langchain Tools/Method Implementation using StructuredTool Implementation for more structured input and output with validation and type safety. THIS IS NOT INTEGRATED WITH THE CODE YET ####

# class FetchProductPriceInput(BaseModel):
#     membership_type: str

# class OnsiteAppointmentTool(StructuredTool):
#     name = "OnsiteAppointment"
#     description = tools_info["OnsiteAppointment"]["description"]

#     def _run(self) -> str:
#         print('Onsite Appointment function is called')
#         return f"Onsite Appointment is booked."

# class FetchProductPriceTool(StructuredTool):
#     name = "PriceInquiry"
#     description = tools_info["PriceInquiry"]["description"]
#     args_schema = FetchProductPriceInput

#     def _run(self, membership_type: str) -> str:
#         print('Fetch product price is called')

#         # Set up the endpoint and headers
#         url = 'https://kno2getherworkflow.ddns.net/webhook/fetchMemberShip'
#         headers = {'Content-Type': 'application/json'}
        
#         # Prepare the data payload with the membership type
#         data = {
#             "membership": membership_type
#         }
        
#         # Send a POST request to the server
#         response = requests.post(url, headers=headers, json=data)
        
#         # Check if the request was successful
#         if response.status_code == 200:
#             # Parse the JSON response to get the price
#             price_info = response.json()
#             return f"The price is ${price_info['price']} per month."
#         else:
#             return "Failed to fetch the price, please try again later."

# class CalendlyMeetingTool(StructuredTool):
#     name = "MeetingScheduler"
#     description = tools_info["MeetingScheduler"]["description"]

#     def _run(self) -> str:
#         print('Calendly Meeting invite is sent.')
#         return f"Calendly meeting invite is sent now."

# class AppointmentAvailabilityTool(StructuredTool):
#     name = "GymAppointmentAvailability"
#     description = tools_info["GymAppointmentAvailability"]["description"]

#     def _run(self) -> str:
#         print('Checking appointment availability.')
#         return f"Our next available appointment is tomorrow, 24th April at 4 PM."