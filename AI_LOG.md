# AI Project Log: portfolio-ask

## Tools Used
For this project, I worked closely with Google Gemini (2.0 Flash) as my primary coding assistant. It helped speed up development by generating boilerplate code and suggesting architectural patterns, while I focused on validating decisions, simplifying complexity, and ensuring the system behaved correctly.

---

## Project Timeline & Workflow

### Day 1: Building the Core (April 24, 2026)
The main focus on day one was getting a clean and reliable retrieval system in place. Initially, the AI leaned toward a more complex reranking setup, but that didn’t align with my goals.

- **Simplifying the Retrieval**  
  I pushed back on the complexity and guided the system toward a simpler approach:  
  *“The current reranking setup feels too complicated. Let’s simplify it by using a Bi-Encoder (`all-MiniLM-L6-v2`) with a basic FAISS flat index.”*

- **Key Decision**  
  I chose to avoid the reranker entirely. While it might have added marginal improvements, it introduced unnecessary “black box” behavior. The Bi-Encoder + FAISS approach was faster, easier to debug, and much more transparent.

- **Debugging the Context Issue**  
  A major issue surfaced where the system failed to connect certain stocks (like TCS and HDFCBANK) with their relevant news. The root cause was a gap in the context mapping pipeline.  
  I manually fixed this logic to ensure proper linkage between tickers and their associated data. This ended up being the most critical debugging step in the project.

---

### Day 2: Refinement & Reliability (April 25, 2026)
With the core functionality working, the focus shifted to usability and trust.

- **Improving the UI**  
  The original interface felt overly flashy due to a large ASCII header. I simplified it with:  
  *“Replace the ASCII art header with a clean, professional single-line banner.”*  
  This made the CLI feel more like a serious financial tool rather than a demo.

- **Strict Grounding Rules**  
  To prevent hallucinations, I enforced a strict rule:  
  *“If the answer isn’t found in the data, respond with ‘Insufficient data to answer.’”*  
  This was a non-negotiable requirement, especially for anything related to financial insights.

---

### Day 3: Finalization & Testing (April 26, 2026)
The final day focused on polish and making the tool feel complete.

- **Graceful Shutdown**  
  Instead of an abrupt exit, I added a proper shutdown flow:  
  *“Simulate cleaning up processes and clearing memory before exiting.”*  
  This small detail improved the overall user experience significantly.

- **Testing & Validation**  
  I ran multiple query scenarios to verify:
  - Grounding rules were consistently enforced  
  - No hallucinated outputs appeared  
  - Context retrieval worked across different stocks  
  - Session history behaved as expected  

---

## Design Philosophy & AI Collaboration
The AI was useful for accelerating development, but it often leaned toward more complex solutions than necessary. I consistently evaluated and challenged those suggestions.

The most important decision was choosing **simplicity over complexity**—specifically, sticking with a FAISS flat index instead of introducing a reranking layer. This made the system easier to understand, debug, and explain without sacrificing performance for this use case.

---

## Time Allocation (12 Hours Total)

- **20% (2.0 hrs) — Planning & Setup**  
  Project setup, environment configuration, and overall structure.

- **20% (2.4 hrs) — Review & Decision Making**  
  Evaluating AI-generated suggestions and selecting the best approach.

- **20% (2.4 hrs) — Manual Development**  
  Writing core logic, especially around `portfolio.json` and data handling.

- **15% (1.8 hrs) — Debugging**  
  Fixing context mapping and ticker-to-news linkage issues.

- **10% (1.2 hrs) — Prompt Engineering**  
  Refining prompts to guide the AI more effectively.

- **10% (1.2 hrs) — Stress Testing**  
  Running multiple queries to ensure reliability and correctness.

- **5% (1.0 hrs) — Research**  
  Reviewing documentation for LangChain and FAISS.

---

## AI Usage Summary
Total time spent working directly with AI: **~4.8 hours (~40%)**

The AI was a strong productivity tool, but the final quality depended heavily on manual validation, simplification, and debugging.