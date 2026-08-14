# Editor Utility: paste PersonalClipboard T3D

Blueprint Mode puts Unreal **T3D** on the Windows clipboard. The editor already round-trips that format: copy nodes in a graph, paste into a text editor, paste back into a graph.

PersonalClipboard does **not** write `.uasset` files. An Editor Utility Widget is a reminder/launcher, not a second serializer.

## Native path (required)

1. Run PersonalClipboard in Blueprint Mode and generate (or `Ctrl+Shift+A` reformats clipboard to T3D).
2. Focus a Blueprint (or Animation/Material) graph in Unreal Editor.
3. `Ctrl+V`.

Validate this path first with [SAMPLE_PRINT_STRING.t3d](SAMPLE_PRINT_STRING.t3d):

1. Open the `.t3d` file in a text editor, select all, copy.
2. In UE5, open any Actor Blueprint → Event Graph.
3. Click empty graph space and paste.
4. You should get a **Print String** node with `InString` = `Hello from PersonalClipboard`.

If paste fails, copy a real Print String from the editor into a text file and diff against the sample — pin names and `FunctionReference` must match your engine version.

## Editor Utility Widget (optional)

`FEdGraphUtilities::ImportNodesFromText` is C++ (`UnrealEd`). Blueprint cannot call it directly. Keep the utility as UX:

1. Enable plugins: **Editor Scripting Utilities**, **Python Editor Script Plugin** (if you want the preview below).
2. Content Browser → right-click → **Editor Utilities → Editor Utility Widget**.
3. Name it `EUW_PasteT3DFromClipboard`.
4. Add:
   - Text block: “Focus a Blueprint graph, then Ctrl+V. PersonalClipboard already owns the clipboard.”
   - Button **Copy sample Print String** — optional, for dry runs.
   - Button **Run Widget** via right-click → **Run Editor Utility Widget**.

Do not add a “import into current asset on disk” button in v1.

### Optional: UE Python preview (does not paste into the graph)

Editor Python can show clipboard length so you know T3D arrived. It still cannot import nodes without a C++ wrapper.

```python
# Paste into the Output Log Python console (Editor)
import unreal

unreal.log("Focus the graph and press Ctrl+V. T3D paste is native to UEdGraph.")
unreal.log("Sample fixture: PersonalClipboard/ue/SAMPLE_PRINT_STRING.t3d")
```

### Later (C++ plugin, out of v1)

A small `UnrealEd` module can wrap:

- `FEdGraphUtilities::CanImportNodesFromText`
- `FEdGraphUtilities::ImportNodesFromText`
- `FEdGraphUtilities::PostProcessPastedNodes`

Expose those as BlueprintCallable for the Editor Utility. Still operate on the **open graph**, not package save.

## Generation rules for the Python app

When `modes/blueprint.py` is implemented:

- Emit only `Begin Object` / `End Object` T3D.
- Mint unique `NodeGuid` and `PinId` (32 hex chars).
- Set `LinkedTo` on **both** ends of every wire.
- Prefer stock `K2Node_CallFunction` / `K2Node_Event` / `K2Node_VariableGet` nodes over custom classes.
- Match this sample’s pin layout before adding new node types.
