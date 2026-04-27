# AI_LOG.md

## Tools used
- I used Google Gemini (specifically Gemini 2.0 Flash) as my main AI coding assistant for this project.

## Significant prompts

1. **Prompt:** "The current reranking setup feels too complicated. Let’s simplify it by using a Bi-Encoder (`all-MiniLM-L6-v2`) with a basic FAISS flat index. Keep the implementation at an intermediate level."
   - **What AI produced:** It refactored the retrieval system to use FAISS with HuggingFace embeddings instead of the heavy reranker approach.
   - **What you kept / what you rejected and WHY:** I rejected the reranker idea because it added unnecessary complexity. I kept the FAISS setup since it is faster, easier to manage, and much simpler to explain.

2. **Prompt:** "The ASCII art header looks a bit too flashy. Replace it with a clean, single-line professional banner, something minimal like Gemini."
   - **What AI produced:** It replaced the ASCII art with a simple, clean header using the Rich library.
   - **What you kept / what you rejected and WHY:** I kept the minimal header and removed the ASCII art. The cleaner look makes the tool feel more professional.

3. **Prompt:** "Make sure the system strictly follows grounding rules. It should not guess or hallucinate. If the answer isn’t found in the data, it should clearly say 'Insufficient data to answer.'"
   - **What AI produced:** It updated the prompts and agent logic to enforce strict grounding and source validation.
   - **What you kept / what you rejected and WHY:** I kept these rules because reliability was critical. This ensures the system only gives answers backed by actual data.

4. **Prompt:** "Instead of a basic exit, create a proper shutdown sequence. It should simulate a real system by cleaning up processes, clearing memory, and exiting gracefully."
   - **What AI produced:** It added a shutdown flow that simulates cleanup steps and logs messages before exiting.
   - **What you kept / what you rejected and WHY:** I kept this because it adds a polished feel to the application and improves the user experience.

## A bug your AI introduced
The AI initially had issues with context mapping. It could not correctly connect general market news to specific stocks like TCS or HDFCBANK. While testing, I noticed it was ignoring relevant news data. I fixed this by improving the context pipeline so the news data maps correctly to portfolio assets.

## A design choice you made against AI suggestion
The AI suggested building a complex retrieval system with an advanced reranker. I chose not to follow that approach and instead used a simpler FAISS flat index with a Bi-Encoder. This made the system easier to understand and explain, while still being effective.

## Time split

*(Based on a total project time of 12 hours)*

- **10% (1.2 hrs)** - Brainstorming ideas, writing prompts, and refining requirements with the AI  
- **20% (2.4 hrs)** - Reviewing AI-generated code and making architecture decisions  
- **20% (2.4 hrs)** - Writing and fixing parts of the code manually (e.g., formatting `portfolio.json`)  
- **15% (1.8 hrs)** - Debugging issues like context mapping and retrieval errors  
- **10% (1.2 hrs)** - Testing the agent with different queries to ensure accuracy  
- **5% (0.6 hrs)** - Referring to LangChain and FAISS documentation when needed  
- **20% (2.4 hrs)** - Overall setup, planning, and running the project  

**Total Time Spent on AI (Prompting, Reviewing & Testing):** ~4.8 hours (about 40% of total time).