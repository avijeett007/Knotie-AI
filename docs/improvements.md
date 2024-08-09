---
title: Further Improvements
description: Suggestions for further improvements and future work on Knotie-AI.
tags: Improvements, Future Work, Knotie-AI
---

# 🚀 Further Improvement Suggestions

Here are some suggestions for further improvements and future work on Knotie-AI:

1. **Update Prompts**: Please update prompts as per your business use cases. The provided prompts in `prompts.py` are very generalized and inspired by the 'SalesGPT' Open Source Project.

2. **Adjust Sales Stages**: Adjust Sales Stages based on your requirement. The current Sales Stages provided in `stages.py` are very generalized and inspired by the 'SalesGPT' Open Source Project.

3. **Test AI Outputs**: If you want to test AI outputs before integrating with Twilio and ElevenLabs API first, use the `testAISalesAgent.py` to do the communication with AI Sales agent in text format. Adjust your prompts accordingly & configuration.

4. **Evaluation Script**: An `testAISalesAgent.py` will be created to allow you to evaluate and test AI Agents before you run it for your use case (This is Completed now).

5. **State Management**: The current code relies on Redis for in-memory state management. File-based and cloud database support will be included for users who can't run Docker in their local (Redis in their local) due to lower system specification. (Work In Progress).

6. **Cloud Deployment Guide**: A guide on how to deploy this on the cloud will be included (Work In Progress).

7. **Wordpress Plugin**: The Wordpress plugin will be updated to support tool calling, email address collection from customers, etc. (Work In Progress).

8. **Suggestions and Feedback**: If you have any other suggestions, please join the [Community](https://community.kno2gether.com/communities/groups/kno2gether-community/home?invite=66b617e90fd0ff23e04efce2) and raise your suggestion or feedback using the **Feedbacks/Suggestions** channel.

9. **Join Private Knotie-AI Channel** : If you wish to contribute as developer or hosting with us, you can get access to our Private Knotie-AI Channel in the Community. Please raise a direct request by sending email to support@kno2gether.com.