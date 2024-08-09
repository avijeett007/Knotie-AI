---
title: 🛠️ Custom Tools and APIs
description: A detailed guide on how to integrate custom tools and APIs with Knotie-AI.
tags: Custom Tools, API Integration, Knotie-AI, Python
---

# 🛠️ Custom Tools and APIs

Integrating custom tools and APIs with Knotie-AI is straightforward. This guide will walk you through the steps required to add and configure your custom tools within the system.

---

## 🧩 Modifying `tools.py`

To add your custom tool:

1. **Open `tools.py`:** Open the `tools.py` file in your preferred IDE.

2. **Remove Existing Tools (Optional):** If you want to clean up the existing tools, you can remove them and keep only your custom tool(s).

3. **Create a New Tool Class:**
   - Define a new class for your tool. Below is an example of a custom tool that fetches pricing information:

   ```python
   class CustomFetchPriceTool(BaseTool):
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
   ```

4. **Customize the Tool:**
   - **Class Name:** Change the class name as desired.
   - **Tool Name:** Update the `name` attribute.
   - **Description:** Provide a clear description of what the tool does.
   - **Target URL:** Modify the target URL in the `_run` method to point to your API.
   - **Data Payload:** Update the payload to fit your API requirements.
   - **Return Message:** Customize the return message to suit your needs.

---

## 📄 Updating `tools_info`

After defining your tool, update the `tools_info` dictionary at the top of the `tools.py` file to include your custom tool:

```python
tools_info = {
    "PriceInquiry": {
        "name": "PriceInquiry",
        "description": "Fetches product prices of Gym memberships.",
        "parameters": {
            "product_name": ["Silver-Gym-Membership", "Gold-Gym-Membership", "Platinum-Gym-Membership"]
        }
    },
    // Add your custom tool information here
}
```

This dictionary is used by the AI model to decide which parameters to use when calling the tool.

---

## 🔧 Modifying `ai_helpers.py`

You are almost done! Just two more steps:

### 1. Initialize the Tool

In the `ai_helpers.py` file, find the following section:

```python
if Config.USE_LANGCHAIN_TOOL_CLASS:
    OnsiteAppointmentTool = OnsiteAppointmentTool()
    FetchProductPriceTool = FetchProductPriceTool()
    CalendlyMeetingTool = CalendlyMeetingTool()
    AppointmentAvailabilityTool = AppointmentAvailabilityTool()
```

- **Remove Unnecessary Tools:** Remove any tools you don’t need and keep only your custom tool. For example:

```python
if Config.USE_LANGCHAIN_TOOL_CLASS:
    CustomFetchPriceTool = CustomFetchPriceTool()
```

### 2. Update the `process_message` Function

In the same `ai_helpers.py` file, locate the `process_message` function:

- **Modify the `if` Statement:** Ensure there’s an `if` statement that matches the `tool_name` with the name you provided in `tools.py`. Here’s an example:

```python
if tool_name == "PriceInquiry":
    tool_output = CustomFetchPriceTool._run(params)  # Ensure params are passed correctly
    message_history.append({"role": "api_response", "content": tool_output})
```

This code calls the `_run` method of your tool when the AI decides to use it.

---

## ⚠️ Important Notes

- **Technical Complexity:** This process involves some technical steps and may require a good understanding of Python and API integration.
- **Future Improvements:** A more user-friendly framework for adding tools (potentially using LangChain) is in the works. Stay tuned for updates!

---

## 🎥 Video Tutorial

For additional help, please watch the tutorial video on YouTube and join our community. If you encounter any issues, feel free to ask for help in the "Ask For Help" channel.


[Watch the Tutorial](https://youtube.com/link-to-video) | [Join the Community](https://discord.com/invite/link)
