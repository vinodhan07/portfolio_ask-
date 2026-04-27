# AI_LOG.md

## Tools used
- I used Google Gemini (specifically Gemini 2.0 Flash) as my main AI coding assistant for this project.

## Significant prompts

1. **Prompt:** "Hey, let's switch from this complex reranking logic to a clean Bi-Encoder (`all-MiniLM-L6-v2`) with a basic FAISS flat index. Keep it at an 'intermediate level'."
   - **What AI produced:** It completely refactored the retrieval code to use FAISS and HuggingFace embeddings instead of the heavy reranker it originally wanted.
   - **What you kept / what you rejected and WHY:** I ditched the AI's first idea (the complex reranker) because it was overkill. I kept the FAISS setup since it's way faster, super reliable, and honestly, a lot easier for me to explain in a technical interview.

2. **Prompt:** "Drop the big ASCII art header, it looks a bit too hacker-ish. Give me a cleaner, single-line professional banner that looks more like Gemini."
   - **What AI produced:** It swapped the chunky text for a slick, single-line header using the Rich library in Python.
   - **What you kept / what you rejected and WHY:** I kept the new minimal header and threw out the old ASCII art. It just makes the whole CLI tool feel much more like an enterprise product.

3. **Prompt:** "You need to follow strict 'Grounding' rules. No guessing, no hallucinations at all. If you can't find the answer in the data, just say 'Insufficient data to answer.'"
   - **What AI produced:** It updated the core system prompts and tweaked the agent's instructions to strictly check its sources before answering.
   - **What you kept / what you rejected and WHY:** I kept these strict grounding rules. I needed to be absolutely sure it wouldn't make things up, and this guarantees it always backs up its answers with actual citations.

4. **Prompt:** "I want a shutdown sequence that feels like a real system powering down. Don't just quit the script—terminate the processes, clear the memory, and disconnect gracefully."
   - **What AI produced:** It wrote a neat little exit sequence that simulates cleanup steps, logs them out, and says goodbye before closing.
   - **What you kept / what you rejected and WHY:** I kept it! It’s a tiny detail, but compared to a boring `sys.exit()`, it makes the app feel incredibly polished.

## A bug your AI introduced
The AI really struggled with context mapping at first. For example, it couldn't figure out how to link general market news to my specific stocks, like TCS or HDFCBANK. I caught this while running some test questions about those specific companies and noticed the agent was completely ignoring the news files I had provided. I had to step in and fix the context pipeline myself so the news data would properly map to the right assets in my portfolio.

## A design choice you made against AI suggestion
At one point, the AI wanted to build this massive, highly complex document retrieval system with an advanced reranker. I straight-up told it no. I forced it to go back to a much simpler FAISS flat index with a Bi-Encoder. I made this choice because I wanted the architecture to be "intermediate level." If I over-engineered it, I'd have a hard time explaining the underlying mechanics to anyone else. Simple was definitely better here.

## Time split
*(Based on a total project time of 12 hours)*

- **10% (1.2 hrs)** - Brainstorming, prompting, and arguing with the AI over features
- **20% (2.4 hrs)** - Reading through the AI's code and making architecture decisions
- **20% (2.4 hrs)** - Actually writing and fixing code myself (like manually formatting the `portfolio.json` file)
- **15% (1.8 hrs)** - Debugging those annoying context mapping and retriever issues
- **10% (1.2 hrs)** - Throwing test questions at the agent to make sure it wasn't hallucinating
- **5% (0.6 hrs)** - Skimming LangChain and FAISS documentation when the AI got stuck
- **20% (2.4 hrs)** - General planning, setup, and running the project

**Total Time Spent on AI (Prompting, Reviewing & Testing):** ~4.8 hours (about 40% of my total time).
