# Workflow Editor
Last updated: 2026-07-20

## Editor Basics
- Drag nodes from the left node tree to the canvas.
- Connect output handles to compatible input handles.
- Use context menu actions such as clone, skip, set global, and remove.
- Use import and export controls for workflow JSON when needed.
- Use compile diagnostics to fix graph errors before execution.
- Use the node context menu to skip or unskip a node; skipped nodes are represented in the compiled plan and execution state.

## Compile Expectations
- Compilation validates graph structure before a run begins.
- Common compile issues include missing inputs, incompatible controllers, missing nodes, and type mismatches.
- Fix compile diagnostics before relying on runtime execution results.
- Diagnostics are retained in the editor after compilation and are classified as blocking errors or non-blocking warnings. Warnings may describe disconnected nodes, missing terminal outputs, disconnected side effects, or conditional branch connections.
- A running workflow can be cancelled from the toolbar. After a reload, the editor can continue monitoring a persisted active run; paused review steps can be resumed when their resume token is available.
