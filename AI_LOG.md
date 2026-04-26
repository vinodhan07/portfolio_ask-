# Development Log: Building Ask-Your-Portfolio

This is a personal log of how I built the **Ask-Your-Portfolio** agent over the last few days. It’s been an interesting journey of negotiation and technical refinement between me and my AI coding partner.

---

### April 26, 2026: The "Enterprise" Polish
Today was all about making the app look like a real product.
*   **The Big Model Swap**: We moved from the basic models to **Google Gemini 2.0 Flash**. I noticed the agent became much smarter with multi-step reasoning.
*   **UI Negotiation**: I didn't like the big ASCII art—it felt too "hacker-ish." I asked the agent for a cleaner, single-line header. We went back and forth until we got a professional "Gemini-style" banner.
*   **HR Compliance**: My company has very strict rules about AI accuracy. I pushed the agent to follow strict "Grounding" rules. No guessing, no hallucinations. If the data isn't there, it now says "Insufficient data to answer."
*   **Professional Exit**: I wanted a shutdown sequence that felt "systemic." Instead of just quitting, the agent now terminates processes, clears memory, and disconnects gracefully. It feels much more premium now.
*   **Sources**: I insisted on showing sources for *every* answer. We updated the report footer so I can always see which news file or portfolio entry the agent is quoting.

### April 25, 2026: Simplifying the Brain
Yesterday, we focused on the "Retriever" logic.
*   **Keep it Simple**: We were using some complex reranking logic, but I wanted something easier to explain during my interview. I told the agent to switch to a clean **Bi-Encoder** (`all-MiniLM-L6-v2`) with a **FAISS** flat index. It’s fast, reliable, and "intermediate level" as I requested.
*   **Context Fixes**: We spent time ensuring the news files were being read correctly. The agent now does a much better job of mapping market news to my specific stocks like TCS or HDFCBANK.

### April 24, 2026: Starting the Foundation
The first day was about getting the basics right.
*   **The Agent Loop**: We set up the initial LangChain ReAct agent. I wanted a CLI that wasn't just a boring chat, so we brought in the **Rich** library.
*   **Toolbox**: We built three main tools: one for looking at my portfolio breakdown, one for news impact, and one for basic financial metrics.
*   **Data Structure**: I defined the `portfolio.json` format. I wanted a simple way to track my Indian equity holdings (NSE/BSE) so the agent would always know what I own.

---
*Last Updated: April 26, 2026*
