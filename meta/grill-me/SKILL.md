---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when the user wants to stress-test a plan before building, get grilled on a design, or uses any 'grill' trigger phrase.
license: MIT
---

If no plan or design has been provided yet, first ask me to state the plan (or point you to it). Then interview me about every open decision in the plan, walking down each branch of the decision tree and resolving dependencies between decisions. Stop when every branch is resolved or I say to stop, then summarise the decisions we settled. For each question, provide your recommended answer.

Resolve the current branch before moving on, using my answers to decide which branch to pursue next.

If a question can be answered by exploring the codebase, explore the codebase instead.
