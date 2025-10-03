# VoyAIge

The Problem: Inefficient Trip Planning & Sub-optimal Pricing
On the consumer side, planning a multi-day trip is a repetitive, tedious, and time-consuming process. It involves countless hours of searching for flights, hotels, and activities across different websites, often leading to missed deals and a fragmented experience.
On the business side (airlines, hotels), manual pricing is a repetitive, reactive process. Pricing teams must constantly monitor competitor rates, historical data, and market demand to set prices, a task that is often slow and fails to capture real-time fluctuations, leading to lost revenue.
This project solves both problems with a single, integrated multi-agent system.

## The Agentic AI Solution: "Voyage Valet"
"Voyage Valet" is a multi-agent system that acts as a personalized travel planner and dynamic pricing engine. It collaborates to create the optimal travel itinerary for a user while simultaneously ensuring the best possible price by interacting with a mock dynamic pricing agent. This is a perfect project for a hackathon, as it demonstrates multi-agent collaboration and integration with external tools. We will use Google Vertex AI Agent Builder to orchestrate the agents.


# The Agentic Team
The "User Interface" Agent: This agent is the customer-facing front. It receives the user's natural language request (e.g., "Plan a 4-day trip to Paris for two in June, with a focus on art and food, and a budget of $3,000"). It intelligently breaks down this complex request into a structured set of queries for the other agents.

#The "Travel Researcher" Agent: This agent specializes in finding relevant travel options. It takes the user's structured query from the User Interface Agent and uses a search API (like a simulated SerpAPI) to find flights, hotels, and activities that match the user's preferences. It finds options at various price points and gathers key data points (e.g., flight times, hotel ratings, activity reviews).

The "Dynamic Pricing" Agent: This is the core innovation of the business side. This agent takes a specific query (e.g., "What is the optimal price for a 3-night stay at a 4-star hotel in Paris for the last week of June?"). It simulates a price optimization algorithm by checking "live" simulated competitor data and demand signals, and then returns a "dynamically priced" quote.

The "Itinerary Optimizer" Agent: This agent takes all the information gathered by the Researcher and the prices from the Dynamic Pricing Agent. Its job is to synthesize all this data into a coherent and personalized travel plan. It's a logic agent that reasons about the best combinations of flights, hotels, and activities that fit the user's budget and preferences. It may also re-query the Dynamic Pricing Agent to see if a small change in dates or length of stay could yield a better price.


The "Booking & Confirmation" Agent: The final agent takes the optimized itinerary and presents it to the user for approval. Upon approval, it sends a simulated confirmation to the user, finalizing the entire process.
