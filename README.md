# ParaGraph LLM Workflow
[![Release](https://img.shields.io/github/v/release/CTCycle/ParaGraph-LLM-workflow?display_name=tag)](https://github.com/CTCycle/ParaGraph-LLM-workflow/releases)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.14-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-22.12.0-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CTCycle Portfolio](https://img.shields.io/badge/CTCycle-Portfolio-58a6ff?style=flat-square)](https://ctcycle.github.io/CTCycle/)
[![CI](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/CTCycle/ParaGraph-LLM-workflow/actions/workflows/ci.yml?query=branch%3Adevelop)

ParaGraph is a local application for planning, running, and observing LLM workflows in a visual way.

It is meant for people who want to assemble a workflow step by step instead of writing everything from scratch. You can connect building blocks, define how information should move through them, run the workflow, and watch what happens as it executes.

The app is organized around a simple idea:

- build a workflow
- prepare the models and provider settings it needs
- run it
- review the result

## What You Can Do

ParaGraph is useful when you want to:

- create workflows using a visual canvas instead of a text-only editor
- connect nodes into a clear sequence of steps
- check whether a workflow is valid before you run it
- launch an execution and follow its progress
- inspect outputs, events, and run history
- manage available nodes, models, and saved configuration profiles
- build retrieval-style workflows that work with documents, embeddings, search, ranking, and answer generation

The app is designed to stay close to the work you are doing. The main screens reflect the main stages of the process:

- build the workflow
- choose the models and settings
- run the workflow
- monitor the result

## Main Screens

Use the app's main navigation to move between these sections.

### Workflow
This is the main workspace.

Use it to:

- place nodes onto the canvas
- connect them into a flow
- adjust node settings
- compile the workflow before starting it
- run the workflow and watch its progress

If you only remember one screen, remember this one. It is where most of the day-to-day work happens.

### Nodes
This area is for exploring what is available.

Use it to:

- browse the node catalog
- search and filter nodes by category
- read short summaries of what each node does
- load ready-made workflow templates
- import custom node manifests when needed

If you are not sure what node to use, start here.

### Models
This area helps you find and prepare models.

Use it to:

- browse Ollama models available to your local setup
- search the Hugging Face catalog
- download models
- track model download progress
- open model cards in the browser

### Configurations
This area is where you prepare the application to run correctly.

Use it to:

- set provider access details when a workflow needs them
- verify local model connectivity
- save and reuse named profiles
- switch between setup profiles without rebuilding everything manually

## How To Get Started

If you are new to the app, the easiest path is:

1. Open **Configurations** and enter the provider or runtime details you need.
2. Open **Workflow** and add the nodes you want to use.
3. Connect the nodes so the workflow has a clear path from start to finish.
4. Compile the workflow to check for missing pieces or incompatible connections.
5. Start the run.
6. Watch the execution status and inspect the output as it arrives.

The workflow does not need to be perfect on the first try. It is normal to build it in small steps, compile often, and adjust as you go.

## A Typical Workflow Session

Most sessions follow the same basic pattern:

1. Start the app.
2. Review or update your settings.
3. Build or open a workflow.
4. Add the nodes you need.
5. Connect the nodes in the order you want them to run.
6. Compile the workflow.
7. Fix anything the compiler points out.
8. Start execution.
9. Monitor the run until it finishes.
10. Review the output and decide what to adjust next.

If your workflow is intended for document retrieval, the usual shape is:

1. Load documents.
2. Split or prepare the content.
3. Create embeddings.
4. Store vectors.
5. Render the query.
6. Search for relevant matches.
7. Rank the results.
8. Build the final answer prompt.
9. Generate the response.

## How To Start The App

### Recommended On Windows

Run:

```powershell
.\start_on_windows.ps1
```

This is the easiest way to start the app locally. The launcher prepares what it needs, starts the backend and frontend, and opens the interface.

The first launch can take longer because the app may still be setting up its local runtime and dependencies. Later launches are usually much faster.

### Manual Startup

If you prefer to start things yourself, see the detailed startup notes in:

- [Startup guide](assets/docs/runtime/startup.md)

## Where To Learn More

For more detailed help, use the dedicated docs:

- [Getting Started](assets/docs/user/getting_started.md)
- [Workflow Editor](assets/docs/user/workflow_editor.md)
- [Models And Configurations](assets/docs/user/models_and_configurations.md)
- [Nodes And Execution](assets/docs/user/nodes_and_execution.md)
- [Troubleshooting And Data](assets/docs/user/troubleshooting_and_data.md)

If you want a broader map of the documentation, start here:

- [Project Overview](assets/docs/project_index.md)

## Troubleshooting

If something does not work as expected:

- try starting the app again
- check that the configuration values are correct
- make sure the model or provider you need is available
- review the workflow compile messages before running
- look at the troubleshooting guide for common causes and data locations

For more detail, see:

- [Troubleshooting And Data](assets/docs/user/troubleshooting_and_data.md)

## Data And Files

The app stores its local runtime data under `app/resources` by default. Set `PARAGRAPH_RESOURCES_DIR` in `settings/.env` to use another absolute or repository-relative location.

That includes things like:

- logs
- workflow data
- downloaded models and related assets
- local database files
- runtime artifacts created while the app is running

## License

This project is licensed under the [MIT License](LICENSE).
