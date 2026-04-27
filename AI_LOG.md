# AI_LOG.md

## Tools used
- Google Gemini (Gemini 2.0 Flash) as the primary AI coding partner and agentic assistant.

## Significant prompts

1. **Prompt:** "Switch from the complex reranking logic to a clean Bi-Encoder (`all-MiniLM-L6-v2`) with a FAISS flat index. Keep it 'intermediate level'."
   - **What AI produced:** A complete refactor of the retrieval pipeline using FAISS and HuggingFace embeddings.
   - **What you kept / what you rejected and WHY:** Rejected the AI's initial complex reranker suggestion. Kept the simple FAISS setup because it is fast, reliable, and much easier to explain during a technical interview.

2. **Prompt:** "Remove the big ASCII art header, it feels too hacker-ish. Make it a cleaner, single-line professional Gemini-style banner."
   - **What AI produced:** A refined, single-line UI header utilizing the Rich library for formatting.
   - **What you kept / what you rejected and WHY:** Kept the new single-line header and rejected the old ASCII art to give the CLI application a more polished, "Enterprise" look.

3. **Prompt:** "Follow strict 'Grounding' rules. No guessing or hallucinations. If the data isn't there, you must reply with 'Insufficient data to answer.'"
   - **What AI produced:** Updated system prompts and agent instructions to enforce strict grounding and source-checking.
   - **What you kept / what you rejected and WHY:** Kept the strict grounding constraints to ensure compliance with strict accuracy rules and to guarantee every answer includes proper source citations.

4. **Prompt:** "Create a shutdown sequence that feels 'systemic'. Instead of just quitting, terminate processes, clear memory, and disconnect gracefully."
   - **What AI produced:** A structured exit sequence with cleanup steps, logging, and a graceful disconnect message.
   - **What you kept / what you rejected and WHY:** Kept this feature because it adds a premium, polished feel to the application's lifecycle compared to a standard abrupt script exit.

## A bug your AI introduced
The AI initially struggled with context mapping in the retriever logic. It couldn't properly associate general market news files with my specific portfolio equity holdings (like TCS or HDFCBANK). I caught this bug by running test queries about specific stocks and noticing the agent ignored relevant news files. I had to intervene and fix the context pipeline to ensure news data was correctly mapped to the right assets.

## A design choice you made against AI suggestion
The AI originally suggested and implemented a highly complex document retrieval system using advanced reranking logic. I explicitly rejected this approach and forced a switch back to a simpler FAISS flat index with a Bi-Encoder. I made this design choice because I needed the architecture to remain "intermediate level" and conceptually straightforward so I could easily explain the underlying mechanics to others, avoiding unnecessary over-engineering.

## Time split
*(Based on a total project time of 12 hours)*

- **10% (1.2 hrs)** Prompting and negotiating features with the AI
- **20% (2.4 hrs)** Reviewing AI output and making architectural decisions
- **20% (2.4 hrs)** Writing and refactoring code manually (setting up `portfolio.json`, formatting)
- **15% (1.8 hrs)** Debugging context mapping and retriever issues
- **10% (1.2 hrs)** Testing the agent's responses for grounding and hallucinations
- **5% (0.6 hrs)** Reading LangChain and FAISS documentation
- **20% (2.4 hrs)** General planning, setup, and execution

**Total Time Spent on AI (Prompting, Reviewing & Testing):** ~4.8 hours (40%)
