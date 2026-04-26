# PORT AGENT: Operational Flow Diagram

This diagram illustrates the logical flow of a user query through the ReAct agent and the specialized internal nodes for news analysis.

```text
                ┌──────────────────────┐
                │      User Query      │
                └─────────┬────────────┘
                          │
                          ▼
                ┌──────────────────────┐
                │   ReAct Agent (LLM)  │
                └─────────┬────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
 allocation_tool   metrics_tool   news_impact_tool
                                          │
                                          ▼
                         ┌─────────────────────────┐
                         │ Node 1: Retrieve News   │
                         └─────────┬───────────────┘
                                   ▼
                         ┌─────────────────────────┐
                         │ Node 2: Tag Holdings    │
                         └─────────┬───────────────┘
                                   ▼
                         ┌─────────────────────────┐
                         │ Node 3: Rank Exposure   │
                         └─────────┬───────────────┘
                                   ▼
                         ┌─────────────────────────┐
                         │ Node 4: LLM Formatting  │
                         └─────────┬───────────────┘
                                   ▼
                         ┌─────────────────────────┐
                         │ Structured JSON Output  │
                         └─────────────────────────┘
```

## Internal Node Breakdown:
1.  **Node 1: Retrieve News**: Performs semantic search on the FAISS vector index to find the most relevant news snippets.
2.  **Node 2: Tag Holdings**: Identifies which stocks in your portfolio are mentioned or impacted by the retrieved news.
3.  **Node 3: Rank Exposure**: Assesses the risk level (High, Medium, Low) and writes the technical rationale.
4.  **Node 4: LLM Formatting**: Synthesizes the final response into the mandated professional prose and structured data.
