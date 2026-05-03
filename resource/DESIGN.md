# Translate Agent — Frontend Design Specification

## Overview

Frontend design for Translate Agent, inspired by Cohere's enterprise command-deck aesthetic. The interface is a polished, professional tool that makes AI conversion feel like serious infrastructure rather than a consumer toy.

---

## 1. Concept & Vision

A bright white canvas with generous 22px rounded cards creating an organic, cloud-like containment language. The dual-typeface system (serif for headlines, geometric sans for body) creates "confident authority meets engineering clarity." Color is used with extreme restraint — black, white, cool grays, with Interaction Blue appearing only on hover/focus states.

---

## 2. Design Language

### Aesthetic Direction
Enterprise command deck: professional without being cold, sophisticated without being intimidating. References: Cohere's marketing site, Linear's precision, Vercel's clarity.

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| Cohere Black | `#000000` | Primary headlines, user message text |
| Near Black | `#212121` | Body links, secondary emphasis |
| Pure White | `#ffffff` | Page background, card surfaces, input backgrounds |
| Lightest Gray | `#f2f2f2` | Subtle card borders, input borders |
| Border Cool | `#d9d9dd` | Section borders, list separators |
| Border Light | `#e5e7eb` | Lighter border variant |
| Muted Slate | `#93939f` | De-emphasized text, captions, placeholders |
| Interaction Blue | `#1863dc` | Hover states, focus rings, active links |
| Ring Blue | `#4c6ee6` | Focus ring color (50% opacity) |
| Focus Purple | `#9b60aa` | Input focus border |
| Snow | `#fafafa` | Elevated subtle surfaces |
| Agent Purple | `#7c3aed` | Assistant avatar & accent (brand color for AI) |

### Typography

- **Display**: `Space Grotesk, Inter, ui-sans-serif, system-ui` — for headlines and the logo
- **Body / UI**: `Inter, -apple-system, BlinkMacSystemFont, ui-sans-serif, system-ui` — for all body text and UI
- **Mono**: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace` — for code blocks

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|------|------|------|--------|-------------|----------------|
| Logo | Space Grotesk | 28px | 500 | 1.1 | 0.5px |
| Message Body | Inter | 14px | 400 | 1.50 | normal |
| Message Code | Mono | 12px | 400 | 1.40 | normal |
| Input Text | Inter | 14px | 400 | 1.50 | normal |
| Caption / Footer | Inter | 12px | 400 | 1.40 | normal |
| Skill Name | Inter | 13px | 500 | normal | normal |
| Skill Desc | Inter | 12px | 400 | normal | normal |

### Spatial System
- Base unit: 8px
- Card padding: 16–24px
- Section spacing: 16–24px
- Input area padding: 0 16px 24px
- Message gap: 16px

### Motion Philosophy
- **Micro-interactions only**: hover color shifts (150ms ease), focus ring transitions (150ms)
- **No decorative animations**: no bounces, slides, or attention-seeking effects
- **Functional transitions**: dropdown appear/disappear (150ms), typing indicator dots

### Visual Assets
- Icons: Inline SVG, 18–20px, stroke-width 1.5–2, currentColor
- Avatars: Single letter (U/A) in rounded squares with brand colors
- No decorative imagery — the white canvas IS the aesthetic

---

## 3. Layout & Structure

### Page Structure
```
┌─────────────────────────────────────────────┐
│  Header (centered logo, minimal)            │
├─────────────────────────────────────────────┤
│                                             │
│  Chat Container (scrollable, flex-grow)     │
│    - Welcome message (centered, muted)      │
│    - Message pairs (user right, agent left)  │
│                                             │
├─────────────────────────────────────────────┤
│  Input Area (fixed at bottom)               │
│    - Input wrapper (22px radius, bordered)  │
│      - File preview (when attached)          │
│      - Textarea                             │
│      - Skills dropdown (above input)        │
│    - Toolbar row                            │
│    - Footer caption                         │
└─────────────────────────────────────────────┘
```

### Responsive Strategy
- Max-width: 768px centered (same as current)
- Mobile: Single column, full-width messages (max-width: 85%)
- Large screens: Comfortable reading width with generous margins

### Visual Pacing
- Header: Minimal presence, 48px vertical padding
- Chat area: Breathing room between messages (16px gap)
- Input area: Anchored at bottom with comfortable padding

---

## 4. Features & Interactions

### Core Features
1. **Text input**: Multi-line textarea, auto-resize up to 200px
2. **File upload**: Click attach button, file preview with remove option
3. **Skills dropdown**: Type `/` to trigger, arrow keys to navigate, Enter/Tab to select, Escape to close
4. **URL detection**: Auto-detect `http://` or `https://` URLs
5. **File type detection**: Auto-detect image, video, or document
6. **Chat mode**: Non-URL, non-file text → agent chat with SSE streaming
7. **Convert mode**: URL or file → conversion endpoint

### Interaction Details

**Send Button**
- Default: Disabled (gray background, no pointer)
- Enabled: Ghost style — transparent background, Cohere Black text
- Hover: Text shifts to Interaction Blue (#1863dc), opacity 0.8
- Active/Sending: Disabled state

**Input Box**
- Border: 1px solid Lightest Gray (#f2f2f2)
- Focus-within: Border shifts to Focus Purple (#9b60aa), subtle box-shadow
- Border-radius: 22px (signature Cohere radius)

**Skills Dropdown**
- Appears above input box
- Border: 1px solid Border Cool (#d9d9dd)
- Border-radius: 8px (comfortable, not 22px — dropdown is secondary)
- Shadow: subtle (0 4px 20px rgba(0,0,0,0.08))
- Item hover: Background shifts to Snow (#fafafa)
- Active item: Left border accent in Interaction Blue

**Message Bubbles**
- User: Cohere Black text on Lightest Gray (#f2f2f2) background, right-aligned
- Assistant: Near Black (#212121) text on Pure White, left-aligned, bordered
- Border-radius: 22px for primary bubbles
- Border: 1px solid Border Light (#e5e7eb) for assistant messages
- No shadows — depth through background contrast

**File Preview in Input**
- Background: Snow (#fafafa)
- Border: 1px solid Border Light (#e5e7eb)
- Border-radius: 8px
- Remove button: Muted Slate, red on hover

**Typing Indicator**
- Three dots, Muted Slate color
- Subtle bounce animation (same as current)
- Inside an assistant message bubble

### Edge Cases
- Empty input: Send button disabled
- File selected: Send button enabled regardless of text
- URL without file: Auto-routes to `/convert/web`
- Long messages: Horizontal scroll in code blocks only
- Stream error: Error message in red (#cf222e) replaces content

---

## 5. Component Inventory

### Header
- **Default**: Logo centered, Space Grotesk 28px, Cohere Black, letter-spacing 0.5px
- **Background**: Pure White with bottom border (1px solid #f2f2f2)

### Chat Container
- **Default**: Scrollable, Pure White background
- **Welcome state**: Centered muted text, 40px top margin

### Message (User)
- **Layout**: Flex row-reverse, gap 12px
- **Avatar**: 32x32px, Cohere Black background, white "U" text, 8px radius
- **Bubble**: Lightest Gray background, Cohere Black text, 22px radius, bottom-right 4px
- **File indicator**: Shows filename with 📎 icon above text

### Message (Assistant)
- **Layout**: Flex row, gap 12px
- **Avatar**: 32x32px, Agent Purple (#7c3aed) background, white "A" text, 8px radius
- **Bubble**: Pure White background, Near Black text, 1px solid #e5e7eb border, 22px radius, bottom-left 4px

### Input Box Wrapper
- **Default**: Pure White background, 1px solid #f2f2f2, 22px radius, subtle shadow
- **Focus-within**: Border #9b60aa, shadow `0 0 0 3px rgba(155,96,170,0.1)`
- **Padding**: 16px

### Textarea
- **Default**: Borderless, transparent background, Inter 14px, Near Black text
- **Placeholder**: Muted Slate color
- **Resize**: None (handled by JS autoResize)

### Skills Dropdown
- **Container**: 240px max-height, scrollable, 8px radius
- **Item default**: Padding 10px 16px, flex between name and description
- **Item hover/active**: Background #fafafa, 2px left border Interaction Blue
- **Skill name**: Inter 13px 500 weight
- **Skill description**: Inter 12px, Muted Slate

### File Preview
- **Container**: Flex row, gap 8px, 8px radius, Snow background
- **Icon**: 20px emoji
- **Filename**: Inter 13px, Near Black
- **Remove**: Muted Slate ✕, red on hover

### Attach Button
- **Default**: 32x32px, transparent bg, Muted Slate icon
- **Hover**: Background #f2f2f2, icon Near Black

### Agent Badge
- **Default**: 12px padding, 1px Border Light border, Snow background, Inter 12px Muted Slate
- **Text**: "Agent" label

### Send Button
- **Default (disabled)**: 32x32px, #e5e5e5 background, #bbb color, not-allowed cursor
- **Enabled**: Ghost — transparent bg, Near Black icon
- **Hover**: Icon #1863dc, opacity 0.8
- **Active**: No change (uses disabled style while processing)

### Footer
- **Default**: Centered Inter 12px, #bbb color, 8px top margin

---

## 6. Technical Approach

### Stack
- Single HTML file with inline structure
- External CSS file (`styles.css`)
- Vanilla JavaScript (`app.js`) — no framework changes needed
- Google Fonts: Space Grotesk + Inter via CDN

### Architecture
- Same JS logic, redesigned CSS only
- CSS custom properties for all design tokens
- BEM-like class naming for clarity
- No external CSS framework dependencies

### Key Implementation Notes
- 22px radius is the signature Cohere radius — applied to input box, message bubbles, primary cards
- Code blocks use mono font at 12px with `#f6f8fa` background (GitHub-inspired, appropriate for technical content)
- Interaction Blue (#1863dc) appears ONLY on hover/focus — never as a static color
- Shadows are minimal; depth comes from background contrast and borders
