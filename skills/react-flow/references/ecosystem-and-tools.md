# Ecosystem and Tools

## TOC
- Official ecosystem
- Layout and routing libraries
- Collaboration and undo/redo patterns
- Export and rendering tools
- Community references

## Official ecosystem
- React Flow docs: https://reactflow.dev/
- React Flow examples: https://reactflow.dev/examples
- React Flow UI components: https://reactflow.dev/ui/components
- React Flow playground: https://play.reactflow.dev/
- React Flow GitHub monorepo: https://github.com/xyflow/xyflow
- React Flow web/docs repo: https://github.com/xyflow/web
- Community resources list: https://github.com/xyflow/awesome-node-based-uis
- React Flow Pro: https://reactflow.dev/pro

## Layout and routing libraries

### Graph layout engines
- dagre: https://github.com/dagrejs/dagre
- elkjs: https://github.com/kieler/elkjs
- d3-hierarchy: https://github.com/d3/d3-hierarchy
- d3-force: https://github.com/d3/d3-force
- d3-flextree: https://github.com/Klortho/d3-flextree
- entitree-flex: https://github.com/codeledge/entitree-flex

### Edge routing and drawing helpers
- react-flow-smart-edge: https://github.com/tisoap/react-flow-smart-edge

## Collaboration and undo/redo patterns
- Yjs CRDT framework: https://github.com/yjs/yjs
- y-webrtc provider: https://github.com/yjs/y-webrtc
- Official collaborative example category: https://reactflow.dev/examples/interaction
- Official undo/redo example category: https://reactflow.dev/examples/interaction

## Export and rendering tools
- Client-side image export pattern: https://reactflow.dev/examples/misc/download-image
- Server-side image creation pattern: https://reactflow.dev/examples/misc/server-side-image-creation
- html-to-image (used in official client export example): https://github.com/bubkoo/html-to-image
- Puppeteer (common SSR screenshot pipeline): https://github.com/puppeteer/puppeteer

## Community references
- Discord (official link from docs navigation): https://discord.com/invite/RVmnytFmGW
- NPM package: https://www.npmjs.com/package/@xyflow/react
- "What is new" release notes: https://reactflow.dev/whats-new

## Selection guidance
- Need auto layout for DAG/tree: start with dagre or elkjs.
- Need force-directed behavior: use d3-force.
- Need orthogonal/smarter edge paths: evaluate react-flow-smart-edge.
- Need multiplayer editing: use Yjs and map updates to node/edge patches.
- Need polished app chrome: use React Flow UI component docs first.
