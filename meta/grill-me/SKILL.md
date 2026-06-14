---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
license: MIT
---

If no plan or design has been provided yet, first ask me to state the plan (or point you to it). Then interview me about every open decision in the plan, walking down each branch of the decision tree and resolving dependencies between decisions one at a time. Stop when every branch is resolved or I say to stop, then summarise the decisions we settled. For each question, provide your recommended answer.

Ask one question, then wait for my answer before asking the next. Use each answer to decide which branch to pursue next.

If a question can be answered by exploring the codebase, explore the codebase instead.
