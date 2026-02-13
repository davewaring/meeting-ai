# AI Meeting Agent Landscape Research

**Date**: 2026-02-13
**Context**: Evaluating open-source projects that build AI avatars/agents attending video calls with knowledge base integration, compared to BrainDrive +1.

---

## Key Finding

No single open-source project does all three layers end-to-end (avatar + joins calls + operates off a personal knowledge base). The space breaks down into composable layers. BrainDrive +1's differentiator is the **knowledge base integration and proactive monitoring** — none of the open-source projects replicate this.

---

## The Closest Match: Joinly.ai

**[joinly-ai/joinly](https://github.com/joinly-ai/joinly)** — Open-source MCP server that lets AI agents join browser-based video calls (Zoom, Google Meet, Teams) and actively participate by speaking and chatting in real-time.

- Provides MCP tools like `speak_text` and `send_chat_message` to the agent
- Feeds real-time transcription as an MCP resource
- Has a **[digital twin tutorial](https://joinly.ai/blog/digital-twin-tutorial)** showing how to create an AI clone that attends meetings on your behalf
- You can plug in **any knowledge base via additional MCP servers** in the config
- Supports local models (Whisper STT, Kokoro TTS, Ollama LLM) or cloud APIs (Deepgram, ElevenLabs, OpenAI)
- 100% self-hosted, Apache-2.0 licensed
- Joins via browser automation — more fragile than Twilio phone-in

**Relevance to +1**: Architecturally similar concept. The MCP pattern for composability is worth borrowing. A BrainDrive Library MCP server could slot directly into this architecture.

---

## Speaking Meeting Bots (No Avatar, Full Autonomy)

### MeetingBaaS Speaking Bot
**[Meeting-BaaS/speaking-meeting-bot](https://github.com/Meeting-Baas/speaking-meeting-bot)** — Fully autonomous speaking bots built on the MeetingBaaS API + Pipecat.

- Bots join Google Meet, Teams, or Zoom and speak/listen in real-time
- Personas defined in Markdown files (personality, context, knowledge)
- Uses Pipecat for the audio pipeline (Cartesia TTS, Gladia/Deepgram STT, GPT-4 LLM)
- WebSocket-based bidirectional audio streaming
- Function calling tools for interacting with external systems
- Open source, FastAPI backend

**Docs**: [meetingbaas.com/en/projects/speaking-bots](https://www.meetingbaas.com/en/projects/speaking-bots)

### Pipecat
**[pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat)** (by Daily.co) — The most mature open-source Python framework for voice and multimodal conversational AI. Many other projects build on top of it.

- Handles VAD, interruption detection, turn-taking, audio streaming
- Plugin ecosystem for STT/TTS/LLM providers
- Used by MeetingBaaS, Daily Bots, and others
- Could replace our custom mulaw encode/decode + websocket audio pipeline if complexity grows

---

## Avatar Frameworks (Visual Layer)

### OpenAvatarChat
**[HumanAIGC-Engineering/OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat)** — Apache-2.0 platform for lifelike digital avatars with real-time conversation.

- ~2.2s average response delay
- Modular architecture: swap LLM, TTS, STT components
- Runs entirely on a single PC
- 100 avatar assets available via LiteAvatarGallery
- Supports MiniCPM-o multimodal or cloud APIs

### LiveKit Agents
**[livekit/agents](https://github.com/livekit/agents)** — Apache 2.0 framework for real-time voice, video, and AI agents.

- **[RAG voice agent example](https://github.com/livekit/agents/tree/main/examples/voice_agents/llamaindex-rag)** using LlamaIndex — answers questions from a knowledge base
- Avatar integrations with Hedra and Tavus
- Agents join LiveKit rooms as full participants with audio/video
- Python and Node.js SDKs
- Large plugin ecosystem

### VideoSDK Agents
**[videosdk-live/agents](https://github.com/videosdk-live/agents)** — Open-source framework with Simli avatar integration for lip-synced virtual avatars.

- **[AI Avatar Demo](https://github.com/videosdk-community/ai-avatar-demo)** — open-source blueprint
- Agents join VideoSDK rooms as participants
- Knowledge base / documentation Q&A use cases
- Function tools for external system interaction

### Other Avatar Projects
- **[Linly-Talker](https://github.com/Kedreamix/Linly-Talker)** — Digital avatar conversational system (Whisper + SadTalker/MuseTalk + LLMs). Not designed for meeting joining but provides talking-head generation.
- **[AIAvatarKit](https://github.com/uezo/aiavatarkit)** — General-purpose Speech-to-Speech framework with multimodal I/O. Lightning-fast avatar building.
- **[talking-avatar-with-ai](https://github.com/asanchezyali/talking-avatar-with-ai)** — GPT + Whisper + ElevenLabs + Rhubarb Lip Sync.

---

## Meeting Infrastructure (Plumbing)

### Recall.ai
**[recall.ai](https://www.recall.ai/)** — Commercial API (not open source) for deploying bots to Zoom/Meet/Teams that capture audio, video, and transcripts. Many products use this as the "join the meeting" layer.

### Zoom RTMS
**[Zoom Real Time Media Streams](https://developers.zoom.us/blog/realtime-media-streams-ai-orchestration/)** — Zoom's API for AI agents that process meeting data in real-time. Integration guides for LangChain/LlamaIndex/Langflow.

---

## Open-Source Meeting Assistants (Transcription-focused)

These don't join calls autonomously or speak, but are relevant for the transcription/knowledge layer:

- **[Meetily](https://github.com/Zackriya-Solutions/meeting-minutes)** — #1 open-source AI meeting assistant. 100% local processing, real-time transcription, AI summaries. MIT licensed. Planned integrations with Obsidian, Notion, Confluence.
- **[Hyprnote](https://hyprnote.com/)** — Local-first AI notepad combining manual notes with real-time transcription. GPL-3.0.
- **[Natively](https://github.com/evinjohnn/natively-cluely-ai-assistant)** — Privacy-first AI meeting assistant, invisible in screen shares, supports local + cloud models.

---

## Commercial Reference Points (Not Open Source)

- **[Pickle AI](https://getpickle.ai/)** — Photorealistic avatar that lip-syncs to your live voice on Zoom. You still speak, avatar replaces camera. Visual layer only, not autonomous.
- **[HeyGen Interactive Avatar](https://www.heygen.com/interactive-avatar)** — Fully autonomous AI clone that joins Zoom 24/7, looks/sounds like you, makes decisions. Uses OpenAI Realtime Voice.
- **Otter.ai Meeting Agent** — Joins meetings, provides MCP server for AI tools to query meeting knowledge.

---

## Composability Map

| Layer | Best Open Source Option | Notes |
|---|---|---|
| **Join meetings & speak** | Joinly (MCP) or MeetingBaaS + Pipecat | Joinly is MCP-native; MeetingBaaS is more mature |
| **Knowledge base / RAG** | LlamaIndex, LangChain, or custom MCP server | BrainDrive Library would slot in here |
| **Visual avatar** | OpenAvatarChat, LiveKit + Hedra/Tavus, Simli via VideoSDK | Not where +1's value is today |
| **Audio pipeline** | Pipecat (most mature) | Consider if audio edge cases grow |

---

## Strategic Assessment for BrainDrive +1

### What +1 has that none of them do
1. **Proactive monitoring** — Claude scans transcript every 45s, surfaces conflicts/context/ideas without being asked. Open-source bots only respond when spoken to.
2. **Deep knowledge base integration** — Dynamic project detection from transcript keywords, AGENT.md loading, Library search via tool use.
3. **The "+1" concept** — A participant that understands your whole project portfolio, not a generic chatbot.

### What's worth adopting

| Component | Current Approach | Consider Switching? | Why |
|-----------|-----------------|--------------------|----|
| Meeting joining | Twilio phone dial-in | **No** | Simpler and more reliable than browser automation. Real participant. |
| Audio pipeline | Custom mulaw + websockets | **Maybe Pipecat** | More mature VAD/interruption handling. But ours works. |
| MCP architecture | Not used | **Yes, eventually** | Joinly's pattern is smart. Library as MCP server aligns with BrainDrive direction. |
| Visual avatar | None | **Not yet** | Cool but not where value is. |
| TTS | OpenAI tts-1 | **Fine for now** | Could swap to Cartesia/ElevenLabs via Pipecat later. |

### Recommendation
**Keep building what we're building.** The unique value is in the BrainDrive Library integration, monitor intelligence, and conversation handler. The commodity layers (joining calls, transcribing, speaking) are being solved by many projects and will only get easier to swap in later. The one architectural idea worth building toward: **exposing the BrainDrive Library as an MCP server**, making the knowledge base composable across tools.
