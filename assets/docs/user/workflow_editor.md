# Workflow Editor
Last updated: 2026-08-26

## Editor Basics
- Drag nodes from the left node tree to the canvas.
- Connect output handles to compatible input handles.
- Blue data ports carry values between nodes. Amber controller ports attach shared providers, memory, or stores.
- Use context menu actions such as clone, skip, and remove.
- Controller ports are explicit graph edges; provider, memory, and store nodes
  are not implicitly attached through node metadata.
- Use import and export controls for workflow JSON when needed.
- Use compile diagnostics to fix graph errors before execution.
- Use the node context menu to skip or unskip a node; skipped nodes are represented in the compiled plan and execution state.

The first blank canvas may offer an optional editor walkthrough. It can be skipped immediately and replayed from the top-bar Help button. The walkthrough does not create or change workflow nodes.

## Compile Expectations
- Compilation validates graph structure before a run begins.
- `Run Workflow` performs compilation automatically before execution; there is no separate compile action in the toolbar.
- Common compile issues include missing inputs, incompatible controllers, missing nodes, and type mismatches.
- Fix compile diagnostics before relying on runtime execution results.
- Diagnostics are retained in the editor after compilation and are classified as blocking errors or non-blocking warnings. Warnings may describe disconnected nodes, missing terminal outputs, disconnected side effects, or conditional branch connections.
- A running workflow can be cancelled from the toolbar. After a reload, the editor can continue monitoring a persisted active run; paused review steps can be resumed when their resume token is available.

## Chat Node
- Add a `Chat` node and connect one `Chat History Memory` or `Chat History
  Persisted` controller to its `history` port.
- Connect the Chat text output through the workflow to exactly one terminal
  output node. Compilation rejects zero or multiple reachable terminal outputs.
- Submit messages from the Chat node itself. Each submission runs the existing
  graph once with a transient message; the message is not serialized into the
  workflow JSON. On success, the selected Chat scope receives the user message
  and final terminal output. Failed, cancelled, or paused runs leave the Chat
  history unchanged.
- Multiple Chat nodes are isolated by their node IDs. `Reset` clears only the
  selected Chat scope. `Reset Run ID` starts a new execution session without
  changing the graph.
- When Chat History is disconnected, the Chat node explains that its `history`
  controller must be connected before messages can be sent. Use Conversation
  help for the full history and terminal-output behavior.

## Text Editing
- Textarea parameters show a compact inline preview with an `Edit` button.
- `Apply` writes the modal draft to the node; `Cancel`, the close button, or
  `Escape` discards the draft. JSON and list parameters keep their specialized
  inline editors.
