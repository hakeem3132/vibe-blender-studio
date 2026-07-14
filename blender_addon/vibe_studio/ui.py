"""Native Blender N-panel for the Milestone 1 beginner workflow."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from ..infrastructure.rpc_security import PROTOCOL_VERSION
from ..infrastructure.rpc_server import rpc_server
from ..version import DISPLAY_VERSION
from .identities import ensure_uuid
from .media_contracts import environment_doctor
from .runtime import VibeRuntime

_runtime: VibeRuntime | None = None
ENABLED_ACTIONS = frozenset(
    {
        "CONNECT",
        "DISCONNECT",
        "RECONNECT",
        "HEALTH",
        "DIAGNOSTICS",
        "PROJECT",
        "INSPECT",
        "REFRESH",
        "SAVE",
        "CHECKPOINT",
        "ASSIGN_ID",
        "REPAIR_IDS",
        "PREVIEW",
        "APPLY",
        "REJECT",
        "UNDO",
        "REDO",
        "CANCEL",
    }
)
MILESTONE_2_ACTIONS = frozenset(
    {
        "MATERIAL_PRESET",
        "STUDIO_LIGHTS",
        "HERO_CAMERA",
        "ROTATE_ANIMATION",
        "PREVIEW_ANIMATION",
        "RENDER_VIDEO",
        "ENVIRONMENT_DOCTOR",
    }
)
ALL_ACTIONS = ENABLED_ACTIONS | MILESTONE_2_ACTIONS


def runtime() -> VibeRuntime:
    global _runtime
    if _runtime is None:
        _runtime = VibeRuntime(bpy)
    return _runtime


class VIBE_PG_State(bpy.types.PropertyGroup):
    project_name: StringProperty(name="Project", default="Untitled Vibe Project")  # type: ignore[valid-type]
    prompt: StringProperty(name="Describe the change", options={"TEXTEDIT_UPDATE"})  # type: ignore[valid-type]
    scope: EnumProperty(  # type: ignore[valid-type]
        name="Scope",
        items=(
            ("SELECTED", "Selected object", "Change only the selected object"),
            ("SCENE", "Current scene", "Create in this scene"),
        ),
        default="SELECTED",
    )
    preserve_unselected: BoolProperty(name="Preserve other objects", default=True)  # type: ignore[valid-type]
    status: StringProperty(name="Status", default="Ready")  # type: ignore[valid-type]
    pending: StringProperty(name="Pending change", default="None")  # type: ignore[valid-type]
    pending_target: StringProperty(name="Target", default="None")  # type: ignore[valid-type]
    pending_properties: StringProperty(name="Properties", default="None")  # type: ignore[valid-type]
    pending_preserve: StringProperty(name="Preserve", default="None")  # type: ignore[valid-type]
    last_health: StringProperty(name="Last health check", default="Never")  # type: ignore[valid-type]
    mode: EnumProperty(  # type: ignore[valid-type]
        name="Mode",
        items=(
            ("SIMPLE", "Simple", "Prompt-first creation"),
            ("CREATOR", "Creator", "Materials, camera and animation presets"),
            ("PROFESSIONAL", "Professional", "Stable IDs and render diagnostics"),
        ),
        default="SIMPLE",
    )
    material_preset: EnumProperty(  # type: ignore[valid-type]
        name="Material",
        items=tuple(
            (value, label, f"Explicit {label} Principled preset")
            for value, label in (
                ("matte", "Matte"),
                ("glossy", "Glossy"),
                ("metal", "Metal"),
                ("glass", "Glass"),
                ("plastic", "Plastic"),
                ("emissive", "Emissive"),
                ("product_black", "Product Black"),
                ("product_white", "Product White"),
            )
        ),
        default="product_black",
    )
    render_preset: EnumProperty(  # type: ignore[valid-type]
        name="Quality",
        items=(
            ("draft", "Draft", "Fast low-cost Eevee output"),
            ("preview", "Preview", "Low-cost composition review"),
            ("balanced", "Balanced", "Moderate Eevee quality"),
            ("high", "High", "Bounded higher-quality output"),
        ),
        default="preview",
    )
    frame_start: IntProperty(name="Start", default=1, min=1, max=10000)  # type: ignore[valid-type]
    frame_end: IntProperty(name="End", default=144, min=1, max=10000)  # type: ignore[valid-type]
    frame_step: IntProperty(name="Step", default=1, min=1, max=100)  # type: ignore[valid-type]
    fps: IntProperty(name="FPS", default=24, min=1, max=240)  # type: ignore[valid-type]
    animation_speed: FloatProperty(name="Speed", default=1.0, min=0.1, max=4.0)  # type: ignore[valid-type]
    output_directory: StringProperty(name="Output", default="frames/final")  # type: ignore[valid-type]
    video_path: StringProperty(name="Video", default="videos/vibe_animation.mp4")  # type: ignore[valid-type]
    render_progress: FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0, subtype="PERCENTAGE")  # type: ignore[valid-type]
    render_state: StringProperty(name="Render", default="Idle")  # type: ignore[valid-type]
    last_preview: StringProperty(name="Preview", default="None")  # type: ignore[valid-type]


class VIBE_OT_Action(bpy.types.Operator):
    bl_idname = "vibe.action"
    bl_label = "Vibe Studio Action"
    bl_options = {"REGISTER"}

    action: StringProperty()  # type: ignore[valid-type]

    def execute(self, context):
        state = context.scene.vibe_studio
        try:
            if self.action not in ALL_ACTIONS:
                raise RuntimeError("Unknown Vibe Studio action")
            if self.action == "CONNECT":
                rpc_server.ensure_running()
                state.status = "Ready for the local backend"
            elif self.action == "DISCONNECT":
                rpc_server.stop()
                state.status = "Disconnected"
            elif self.action == "RECONNECT":
                rpc_server.stop()
                rpc_server.start()
                state.status = "Reconnected"
            elif self.action == "HEALTH":
                state.status = "Healthy" if rpc_server.is_listener_healthy() else "Backend unavailable"
                state.last_health = time.strftime("%H:%M:%S")
            elif self.action == "DIAGNOSTICS":
                path = runtime().diagnostics(rpc_server)
                state.status = f"Diagnostics saved: {path.name}"
            elif self.action == "PROJECT":
                ensure_uuid(context.scene)
                context.scene["vibe_project_name"] = state.project_name
                state.status = "Project metadata created"
            elif self.action in {"INSPECT", "REFRESH"}:
                summary = runtime().inspect()
                state.status = f"Scene inspected: {summary['object_count']} objects"
            elif self.action == "SAVE":
                if not bpy.data.filepath:
                    raise RuntimeError("Choose a .blend path with File > Save As first")
                bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath)
                state.status = "Project saved"
            elif self.action == "CHECKPOINT":
                bpy.ops.ed.undo_push(message="Vibe Studio checkpoint")
                state.status = "Checkpoint created"
            elif self.action == "ASSIGN_ID":
                if context.active_object is None:
                    raise RuntimeError("Select an object first")
                state.status = f"Stable ID: {ensure_uuid(context.active_object)}"
            elif self.action == "REPAIR_IDS":
                repaired = runtime().repair_identities()
                state.status = f"Identity repair complete: {len(repaired)} repaired"
            elif self.action == "PREVIEW":
                transaction = runtime().preview_prompt(
                    state.prompt,
                    scope=state.scope,
                    preserve_unselected=state.preserve_unselected,
                )
                state.pending = f"{transaction.change_set.intent} · low risk · verified"
                operation = transaction.change_set.operations[0]
                state.pending_target = operation.target_id or "New object"
                state.pending_properties = ", ".join(operation.parameters)
                state.pending_preserve = ", ".join(transaction.change_set.preserve)
                state.status = "Preview verified; scene unchanged"
            elif self.action == "APPLY":
                transaction = runtime().active_transactions().apply_pending()
                state.pending = "None"
                state.pending_target = "None"
                state.status = f"Applied {transaction.change_set.intent}"
            elif self.action == "REJECT":
                runtime().active_transactions().reject()
                state.pending = "None"
                state.pending_target = "None"
                state.status = "Change rejected; scene unchanged"
            elif self.action == "UNDO":
                runtime().active_transactions().undo()
                state.status = "Last Vibe change undone"
            elif self.action == "REDO":
                runtime().active_transactions().redo()
                state.status = "Last Vibe change redone"
            elif self.action == "CANCEL":
                runtime().cancelled = True
                runtime().render_queue.cancel()
                cancelled = runtime().cancel_background_render()
                if cancelled is not None:
                    state.render_progress = cancelled.progress
                    state.render_state = "Cancelled; completed frames preserved"
                state.status = "Current action cancelled"
            elif self.action == "MATERIAL_PRESET":
                target_id = runtime().selected_id()
                if target_id is None:
                    raise RuntimeError("Select a mesh object first")
                material_id = runtime().create_and_assign_material(target_id, state.material_preset)
                state.status = f"Material assigned: {material_id[:8]}"
            elif self.action == "STUDIO_LIGHTS":
                target_id = runtime().selected_id()
                if target_id is None:
                    raise RuntimeError("Select the product object first")
                light_ids = runtime().create_studio_lighting(target_id)
                state.status = f"Three-point studio created: {len(light_ids)} lights"
            elif self.action == "HERO_CAMERA":
                target_id = runtime().selected_id()
                if target_id is None:
                    raise RuntimeError("Select the product object first")
                camera_id = runtime().create_hero_camera(target_id)
                state.status = f"Hero camera active: {camera_id[:8]}"
            elif self.action == "ROTATE_ANIMATION":
                target_id = runtime().selected_id()
                if target_id is None:
                    raise RuntimeError("Select the object to animate")
                if state.frame_end < state.frame_start:
                    raise RuntimeError("End frame must be after the start frame")
                context.scene.frame_start = state.frame_start
                context.scene.frame_end = state.frame_end
                context.scene.render.fps = state.fps
                runtime().animate_rotation(target_id, frame_start=state.frame_start, frame_end=state.frame_end)
                state.status = f"Rotation animation created: frames {state.frame_start}-{state.frame_end}"
            elif self.action == "PREVIEW_ANIMATION":
                if context.scene.camera is None:
                    raise RuntimeError("Create and activate a camera before previewing")
                path = runtime().render_preview_frame("previews/current", context.scene.frame_current)
                state.last_preview = str(path.name)
                state.status = f"Rendered preview: {path.name}"
            elif self.action == "RENDER_VIDEO":
                if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
                    raise RuntimeError("FFmpeg and FFprobe are required for MP4 export")
                state.render_state = "Starting background render"
                state.render_progress = 0.0
                job = runtime().create_render_job(
                    state.output_directory,
                    frame_start=state.frame_start,
                    frame_end=state.frame_end,
                    frame_step=state.frame_step,
                    preset=state.render_preset,
                    resolution_x=640,
                    resolution_y=360,
                    resolution_percentage=50 if state.render_preset in {"draft", "preview"} else 100,
                )
                snapshot = runtime().start_background_render(job)
                state.render_progress = snapshot.progress
                state.render_state = "Rendering in background"
                state.status = "Background render started; Blender remains responsive"
                bpy.ops.vibe.render_monitor("INVOKE_DEFAULT")
            elif self.action == "ENVIRONMENT_DOCTOR":
                root = runtime().project_root() if bpy.data.filepath else Path.cwd()
                report = environment_doctor(
                    root,
                    blender=bpy.app.binary_path,
                    ffmpeg=shutil.which("ffmpeg"),
                    ffprobe=shutil.which("ffprobe"),
                )
                available = sum(item["status"] == "available" for item in report.values())
                state.status = f"Environment Doctor: {available}/{len(report)} checks available"
        except Exception as exc:
            state.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class VIBE_OT_RenderMonitor(bpy.types.Operator):
    bl_idname = "vibe.render_monitor"
    bl_label = "Monitor Vibe Background Render"
    bl_options = {"INTERNAL"}

    _timer = None

    def _finish(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def invoke(self, context, _event):
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        state = context.scene.vibe_studio
        if event.type == "ESC":
            runtime().cancel_background_render()
            state.render_state = "Cancelled; completed frames preserved"
            state.status = "Background render cancelled"
            self._finish(context)
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        try:
            snapshot = runtime().poll_background_render()
            state.render_progress = snapshot.progress
            state.render_state = f"Background render: {snapshot.status.lower()}"
            if snapshot.status == "COMPLETED":
                state.render_state = "Encoding verified MP4"
                probe = runtime().finish_background_video(state.video_path)
                state.render_progress = 1.0
                state.render_state = "Completed"
                state.status = f"MP4 verified: {probe['streams'][0]['width']}x{probe['streams'][0]['height']}"
                self._finish(context)
                return {"FINISHED"}
            if snapshot.status in {"FAILED", "CANCELLED"}:
                state.status = snapshot.error or "Background render cancelled; completed frames preserved"
                self._finish(context)
                return {"CANCELLED"}
        except Exception as exc:
            state.render_state = "Failed"
            state.status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            self._finish(context)
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


def _button(layout, label: str, action: str, icon: str = "NONE"):
    operator = layout.operator("vibe.action", text=label, icon=icon)
    operator.action = action


class VIBE_PT_Studio(bpy.types.Panel):
    bl_label = "Vibe Studio"
    bl_idname = "VIBE_PT_studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"

    def draw(self, context):
        layout = self.layout
        state = context.scene.vibe_studio
        layout.prop(state, "mode", expand=True)
        connection = layout.box()
        connection.label(text="Connection", icon="LINKED")
        connection.label(text="Connected" if rpc_server.last_authenticated_at else "Waiting for backend")
        connection.label(text=f"Add-on/backend {DISPLAY_VERSION} · Protocol {PROTOCOL_VERSION}")
        connection.label(text=f"Last health check: {state.last_health}")
        if not rpc_server.is_listener_healthy():
            connection.label(text="Choose Connect, then start the local backend", icon="INFO")
        row = connection.row(align=True)
        _button(row, "Connect", "CONNECT")
        _button(row, "Disconnect", "DISCONNECT")
        _button(row, "Reconnect", "RECONNECT")
        row = connection.row(align=True)
        _button(row, "Health check", "HEALTH")
        _button(row, "Diagnostics", "DIAGNOSTICS")

        project = layout.box()
        project.label(text="Project", icon="FILE_BLEND")
        project.prop(state, "project_name")
        scene = context.scene
        project.label(text=f"Scene: {scene.name} · Objects: {len(scene.objects)}")
        project.label(text=f"Path: {bpy.data.filepath or 'Not saved'}")
        project.label(text=f"Camera: {scene.camera.name if scene.camera else 'None'}")
        project.label(text=f"File status: {'Unsaved changes' if getattr(bpy.data, 'is_dirty', False) else 'Saved'}")
        project.label(text=f"Frames: {scene.frame_start}-{scene.frame_end} · FPS: {scene.render.fps}")
        row = project.row(align=True)
        _button(row, "Create", "PROJECT")
        _button(row, "Inspect", "INSPECT")
        _button(row, "Refresh", "REFRESH")
        row = project.row(align=True)
        _button(row, "Save", "SAVE")
        _button(row, "Checkpoint", "CHECKPOINT")
        row = project.row(align=True)
        _button(row, "Assign selected ID", "ASSIGN_ID")
        _button(row, "Repair IDs", "REPAIR_IDS")

        prompt = layout.box()
        prompt.label(text="Describe one object change", icon="OUTLINER_OB_MESH")
        prompt.prop(state, "prompt", text="")
        prompt.prop(state, "scope")
        prompt.prop(state, "preserve_unselected")
        row = prompt.row(align=True)
        _button(row, "Preview", "PREVIEW", "HIDE_OFF")
        _button(row, "Apply", "APPLY", "CHECKMARK")
        _button(row, "Reject", "REJECT", "X")
        row = prompt.row(align=True)
        _button(row, "Undo", "UNDO")
        _button(row, "Redo", "REDO")
        _button(row, "Stop", "CANCEL")

        pending = layout.box()
        pending.label(text="Pending change")
        pending.label(text=state.pending)
        pending.label(text=f"Target: {state.pending_target[:36]}")
        pending.label(text=f"Properties: {state.pending_properties}")
        pending.label(text=f"Preserve: {state.pending_preserve[:48]}")
        pending.label(text=state.status)
        history = runtime().active_transactions().history[-5:]
        if history:
            pending.label(text="Recent history")
            for transaction in reversed(history):
                target = transaction.target_ids[0][:8] if transaction.target_ids else "new object"
                timestamp = time.strftime("%H:%M:%S", time.localtime(transaction.timestamp))
                pending.label(text=f"{timestamp} · {transaction.status} · {target}")
                pending.label(text=transaction.change_set.prompt[:48])


class VIBE_PT_Create(bpy.types.Panel):
    bl_label = "Create"
    bl_idname = "VIBE_PT_create"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        layout = self.layout
        state = context.scene.vibe_studio
        layout.label(text="Use the Prompt panel to create bounded objects.")
        if state.mode != "SIMPLE":
            layout.label(text="Creator presets are grouped below.")


class VIBE_PT_Materials(bpy.types.Panel):
    bl_label = "Materials"
    bl_idname = "VIBE_PT_materials"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        state = context.scene.vibe_studio
        self.layout.prop(state, "material_preset")
        row = self.layout.row()
        row.enabled = context.active_object is not None and context.active_object.type == "MESH"
        _button(row, "Create and assign", "MATERIAL_PRESET", "MATERIAL")


class VIBE_PT_Lighting(bpy.types.Panel):
    bl_label = "Lighting"
    bl_idname = "VIBE_PT_lighting"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        row = self.layout.row()
        row.enabled = context.active_object is not None
        _button(row, "Three-point studio", "STUDIO_LIGHTS", "LIGHT_AREA")


class VIBE_PT_Camera(bpy.types.Panel):
    bl_label = "Camera"
    bl_idname = "VIBE_PT_camera"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        row = self.layout.row()
        row.enabled = context.active_object is not None
        _button(row, "Hero product camera", "HERO_CAMERA", "CAMERA_DATA")
        if context.scene.camera:
            self.layout.label(text=f"Active: {context.scene.camera.name}")


class VIBE_PT_Animate(bpy.types.Panel):
    bl_label = "Animate"
    bl_idname = "VIBE_PT_animate"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        state = context.scene.vibe_studio
        if state.mode != "SIMPLE":
            row = self.layout.row(align=True)
            row.prop(state, "frame_start")
            row.prop(state, "frame_end")
            self.layout.prop(state, "fps")
            self.layout.prop(state, "animation_speed")
        row = self.layout.row()
        row.enabled = context.active_object is not None
        _button(row, "Create 360° rotation", "ROTATE_ANIMATION", "KEYFRAME_HLT")
        row = self.layout.row()
        row.enabled = context.scene.camera is not None and bpy.data.filepath != ""
        _button(row, "Preview animation frame", "PREVIEW_ANIMATION", "RENDER_STILL")


class VIBE_PT_Render(bpy.types.Panel):
    bl_label = "Render"
    bl_idname = "VIBE_PT_render"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        state = context.scene.vibe_studio
        self.layout.prop(state, "render_preset")
        if state.mode != "SIMPLE":
            row = self.layout.row(align=True)
            row.prop(state, "frame_start")
            row.prop(state, "frame_end")
            row.prop(state, "frame_step")
            self.layout.prop(state, "output_directory")
            self.layout.prop(state, "video_path")
        self.layout.prop(state, "render_progress", slider=True)
        self.layout.label(text=state.render_state)
        row = self.layout.row()
        row.enabled = bool(
            context.scene.camera and bpy.data.filepath and shutil.which("ffmpeg") and shutil.which("ffprobe")
        )
        _button(row, "Render verified MP4", "RENDER_VIDEO", "RENDER_ANIMATION")
        if not row.enabled:
            self.layout.label(text="Save project, add a camera, and install FFmpeg", icon="INFO")
        _button(self.layout, "Cancel render", "CANCEL", "CANCEL")


class VIBE_PT_Diagnostics(bpy.types.Panel):
    bl_label = "Diagnostics"
    bl_idname = "VIBE_PT_diagnostics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, context):
        state = context.scene.vibe_studio
        _button(self.layout, "Environment Doctor", "ENVIRONMENT_DOCTOR", "PREFERENCES")
        if state.mode == "PROFESSIONAL":
            active = context.active_object
            self.layout.label(text=f"Object ID: {(active.get('vibe_uuid') if active else 'None')}")
            camera = context.scene.camera
            self.layout.label(text=f"Camera ID: {(camera.get('vibe_uuid') if camera else 'None')}")
            self.layout.label(text=f"Engine: {context.scene.render.engine}")
            self.layout.label(text=f"Last preview: {state.last_preview}")


class VIBE_PT_History(bpy.types.Panel):
    bl_label = "History"
    bl_idname = "VIBE_PT_history"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Vibe Studio"
    bl_parent_id = VIBE_PT_Studio.bl_idname

    def draw(self, _context):
        transactions = runtime().active_transactions().history[-10:]
        if not transactions:
            self.layout.label(text="No Vibe changes yet")
            return
        for transaction in reversed(transactions):
            target = transaction.target_ids[0][:8] if transaction.target_ids else "scene"
            timestamp = time.strftime("%H:%M:%S", time.localtime(transaction.timestamp))
            self.layout.label(text=f"{timestamp} · {transaction.status} · {target}")
            self.layout.label(text=transaction.change_set.prompt[:56])


CLASSES = (
    VIBE_PG_State,
    VIBE_OT_Action,
    VIBE_OT_RenderMonitor,
    VIBE_PT_Studio,
    VIBE_PT_Create,
    VIBE_PT_Materials,
    VIBE_PT_Lighting,
    VIBE_PT_Camera,
    VIBE_PT_Animate,
    VIBE_PT_Render,
    VIBE_PT_History,
    VIBE_PT_Diagnostics,
)


def register_ui() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vibe_studio = PointerProperty(type=VIBE_PG_State)


def unregister_ui() -> None:
    global _runtime
    del bpy.types.Scene.vibe_studio
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    _runtime = None
