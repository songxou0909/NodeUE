import sys
import re
import os
import uuid
import json
import shutil
import platform
import tempfile
import datetime
import urllib.request
import urllib.error
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QGraphicsView, QGraphicsScene, 
    QGraphicsItem, QGraphicsPathItem, QGraphicsObject, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QGraphicsProxyWidget, QTextEdit, QLabel, QCheckBox, QFrame,
    QListWidget, QListWidgetItem, QInputDialog, QMenu, QComboBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QDockWidget
)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QTimer, QSize, QEvent, QUrl, QThread, QSettings
from PySide6.QtGui import (
    QBrush, QPen, QColor, QFont, QPainter, QPainterPath, QLinearGradient, QPolygonF, QIcon, QKeySequence, QCursor, QPainterPathStroker, QPixmap,
    QTransform, QFontMetricsF, QDesktopServices, QTextCursor, QTextCharFormat, QTextBlockFormat
)

SPEC_INSTRUCTIONS = r"""File Format Specification: The file must contain Node Definitions and Link Connections.
Treat this as a reference for all the Text Graph you are going to generate later on.
You MUST export text using a code block and make sure to export plain text to avoid format problems (e.g., Text displayed in Latex) because it contains special character markdowns.

Each line must follow one of these two formats:

1. Node Definition: Use this to define a node and its available pins.
Format: NodeName_UniqueID (Input1; Input2;) : (Output1; Output2;)

Important: You MUST use semicolons (;) to end a pin. Do NOT use commas.
This allows you to use commas inside pin values, e.g., Color\(1,0,0\).
Each pin MUST end with a semicolon, thus, a pin with no text is allowed

Unique Names Rule:
If the logic requires multiple nodes of the same type (e.g., two "PrintString" nodes), you MUST give them unique names (e.g., PrintString_1, PrintString_2).

*Visual Note:* The visualizer will automatically hide the "_Number" suffix.
In the UI, "PrintString_1" and "PrintString_2" will both simply display as "PrintString".
Node names are in PascalCase (UpperCamelCase) style, with no space, so it should be "PrintString" instead of "Print String".
Use the node name as what it will appear in UI of UE5, e.g., use "Branch" but not "Branch_VariableA", then add the suffix.
If you intend to add a new node of the same type appeared in the text graphthat the user provided, make sure you use the same node name with a unique suffix.
If you intend to adjust the flow of an existing node in the user's text graph, make sure you use the same node name and same suffix to represent the same node.
ALWAYS use unique IDs in this text file to ensure the logic works.

Example: GetActorLocation (Target) : (Location)

2. Link Connection: Use this to connect two nodes together.
SourceNode (SourcePinName) -> TargetNode (TargetPinName)
(Note: Links still use standard syntax, no semicolons needed here as it maps 1 pin to 1 pin).
*Rule:* When linking to a pin that has a default value (e.g. "Duration\(0.2\)"), use ONLY the Label name in the link (e.g. "Duration").

3. Pin Rules (Crucial): The visualizer determines the Shape (Triangle vs Circle) and Layout based on the Pin Name.

[Execution Pins] (White Triangles, Top Row)
To create a standard execution flow, use the specific names:
 - inExec  (for Left/Input side)
 - outExec (for Right/Output side)
Other valid Execution Output names: Then, Completed, True, False, Loop Body, OnClicked, Released, Update, Finished, CastFailed, IsValid, NotValid, etc.

[Data Pins with Values] (Label + Editable Box)
To create a UE5-style input pin with an editable value, you MUST use the escaped format: Label\(Value\)
Important: The parentheses wrapping the value MUST be preceded by a backslash.
This prevents errors when the Label itself contains parentheses (e.g., "Rotation (Roll)").
Syntax: PinName\(DefaultValue\)

Example (String): InString\("Hello World"\)
Example (Float): Duration\(0.2\)
Example (Vector): Location\(0, 0, 0\)
Example (Complex Name): New Rotation X (Roll)\(0.0\)
Example (Boolean): Condition\(True\)

Any simple name (e.g., Target, Location, Instigator) without the escaped value syntax will be rendered as a standard data pin circle.
*Tip: Gold standard is to follow the look of the nodes in the actual Unreal Engine Blueprint system.*

4. Special Node Rules (Visualizer Specifics):

[Pure Nodes] (Getters, Math, Logic)
Nodes that do not change the execution flow (Pure Nodes) MUST NOT have "Exec" pins.
Example: GetPlayerHealth (Target\(self\);) : (Health;)

[Math Nodes]
To trigger the "Compact Math Visual" (Small node with symbol), name the node starting with standard operations:
Add, Subtract, Multiply, Divide, Equal, Less, Greater, And, Or, Not.

*Critical:* Do NOT use these names if the node is an Action (e.g., do not name a node "Add" if it is actually "AddComponent"). The visualizer checks for words like "Component", "To", "Screen" to prevent false positives.

[Delegate Pins]
To create the Red Square Delegate pin (for Event Dispatchers), the pin name MUST contain "OutputDelegate" (with no space).
Example: BindEvent (outExec; OutputDelegate;) : (Then;)

5. Coordinates (Input Context Only):
The input text may contain a section for coordinates.
Ignore this section completely. Do NOT generate coordinates in your output.
CRITICAL: However, you MUST preserve the exact Node Names (e.g. "Add_1", "PrintString_5").
Do not change the "_Number" suffix. This ensures the logic maps back to the existing visual layout.
If a new node is needed, use a different suffix to distinguish from current nodes.

6. Consistency Rule:
The links MUST connect to the pins defined in the Node Definitions section, you cannot create non-exisiting pins in the Links section that are not defined in the Node Definitions section

7. Logic Rule (UE5 Standards):
You MUST obey the linking logics in the blueprint system in UE5 (Unreal Engine 5), e.g., an output pin of a node cannot be connect to an output pin of another node, etc.

8. Export Format:
You MUST export text using a code block or plain text to avoid format problems (e.g., Text displayed in Latex) because it contains special character markdowns

The pin follows the look as the blueprint system in UE5, thus there may be some pins hidden and will not show in this simplified text, do not count as an error (for critical and logic errors, you must point it out and correct it).
The purpose is to check and validate whether the logic of the flow is correct and sound (the most important), but if there are some case differences or minor errors due to the habits or script flaw, do not count as an error (but for critical and logic related errors, you must point it out and correct it).
However, for any kind of error, you can make a comment in the end (of the conversation or chat, not the Output Text) to remind the user.
You MUST export text using a code block or plain text to avoid format problems (e.g., Text displayed in Latex) because it contains special character markdowns

Example Output Text:

# --- Node Definitions ---
AddIntInt_1 (A; B;) : (Return Value;)
EventAddResource_1 () : (outExec; OutputDelegate; Resource; Value;)
GetGameInstance_1 () : (Return Value;)
GetResources_1 () : (Resources;)
GetResources_2 () : (Resources;)
MapAdd_1 (inExec; Target Map; Key; Value;) : (outExec;)
MapFind_1 (Target Map; Key;) : (Value; Return Value;)
UpdateAllResources_1 (inExec; Target; New Param;) : (outExec;)
UpdateResources_1 (inExec; Target\(self\); Resource; Value;) : (outExec;)

# --- Links ---
GetResources_1 (Resources) -> MapFind_1 (Target Map)
GetResources_1 (Resources) -> MapAdd_1 (Target Map)
UpdateResources_1 (outExec) -> UpdateAllResources_1 (inExec)
GetGameInstance_1 (Return Value) -> UpdateAllResources_1 (Target)
GetResources_2 (Resources) -> UpdateAllResources_1 (New Param)
EventAddResource_1 (outExec) -> MapAdd_1 (inExec)
EventAddResource_1 (Resource) -> UpdateResources_1 (Resource)
EventAddResource_1 (Resource) -> MapFind_1 (Key)
EventAddResource_1 (Resource) -> MapAdd_1 (Key)
EventAddResource_1 (Value) -> AddIntInt_1 (A)
MapFind_1 (Value) -> AddIntInt_1 (B)
MapFind_1 (Value) -> UpdateResources_1 (Value)
MapAdd_1 (outExec) -> UpdateResources_1 (inExec)
AddIntInt_1 (Return Value) -> MapAdd_1 (Value)

"""

# ==========================================
#        TRANSLATION SYSTEM
# ==========================================
SPEC_EN = r"Do NOT reply yet, wait for the user to provide the text graph; Current user language is English." + f"\n" + SPEC_INSTRUCTIONS
SPEC_CN = r"Do NOT reply yet, wait for the user to provide the text graph; Current user language is Chinese, reply mainly in Chinese, do NOT use Chinese for the entire Output Text including # --- Node Definitions --- and # --- Links ---." + f"\n" + SPEC_INSTRUCTIONS

# Define the Dictionary
TRANSLATIONS = {
    "EN": {
        "window_title": "UE5 Blueprint Viewer",
        "btn_show": "Show Current",
        "btn_mode_simple": "Simplified",
        "btn_mode_raw": "Raw Text",
        "btn_sort": "Auto Sort",
        "chk_coords": "Node Coords",
        "tip_coords": "If checked, the <Simplified> text in <Show Current> will include coordinates",
        "btn_spec": "Spec",
        "btn_copy1":"Copy",
        "btn_copy2":"Copied!",
        "search_placeholder": "Search...",
        "spec_text": SPEC_EN,
        # Dialog: Edit Node
        "dlg_edit_title": "Edit Node",
        "lbl_node_name": "Node Name:",
        "lbl_inputs": "Inputs (semicolon sep):",
        "lbl_outputs": "Outputs (semicolon sep):",
        "btn_ok": "OK",
        "btn_cancel": "Cancel",
        "btn_delete": "Delete Node",
        "msg_del_title": "Confirm Delete",
        "msg_del_text": "Are you sure you want to delete this node?",
        # Dialog: Paste
        "dlg_paste_title": "Paste Graph Text",
        "dlg_paste_holder": "Paste your node text here...",
        "import_template":"Import Node Template",
        # Dialog: Show
        "dlg_show_title": "Current Graph Text",
        "tip_no_raw": "Raw text unavailable",
        "tip_has_raw":"Raw text available",
        "dlg_spec_title": "File Format Specification",
        # Dialog: Errors
        "msg_err_title": "Error",
        "msg_conv_err": "Failed to convert raw UE data: ",
        "msg_parse_err": "Failed to parse file: ",
        # Setting
        "btn_setting": "Setting",
        "dlg_setting_title": "Settings",
        "chk_enable_save": "Enable saving",
        "tip_enable_save": "Create a folder for this program <NodeUE>, including config file and template\nWhen unchecked, the whole folder will be deleted including the template and blueprints, make sure you change the saving path or make a backup if you want to keep them",
        "btn_update_path": "Change Saving Path",
        "tip_update_path": "Change the saving path\nExisting files will be moved (Config file excluded), no trash files will be left\nIf you want to delete the config file, please use the <Delete Config File> button",
        "btn_del_config": "Delete Config File",
        "tip_del_config": "Delete preference file, program will forget custom paths",
        "lbl_setting_instr": "Program will generate a template file and load it on start\nNew nodes from drag-drop/paste will be merged",
        "msg_del_config_title": "Delete Config",
        "msg_del_config_text": "Are you sure? This will reset all preferences",
        "msg_disable_save_title": "Disable Saving",
        "msg_disable_save_text": "Unchecking will delete the whole <NodeUE> folder\nCannot recover, Confirm?",
        "msg_copy_err": "You have copied node(s) without raw text",
        "msg_import_stat": "Detected: {}; Duplicated: {}; New: {}; Total: {}",
        "msg_tpl_missing": "Cannot find template file at: {}",
        "msg_path_updated": "Template path updated successfully",
        "msg_config_deleted": "Config deleted, restart program to reset",
        "msg_tpl_loaded": "Templates Loaded: {}",
        "msg_pasted": "Pasted {} nodes",
        "lbl_curr_path": "Current Path: {}",
        # BP saving
        "btn_open_bp": "Open Blueprint",
        "btn_save_bp": "Save Blueprint",
        "dlg_open_bp_title": "Open Saved Blueprint",
        "lbl_open_bp": "Select a blueprint to open:",
        "dlg_save_bp_title": "Save Blueprint",
        "lbl_save_bp": "Enter Blueprint Name:",
        "msg_bp_saved": "Blueprint saved successfully!",
        "msg_bp_exists": "Blueprint '{}' already exists. Overwrite?",
        "msg_bp_err": "Error saving/loading blueprint: {}",
        "msg_no_bp": "No saved blueprints found",
        "msg_enable_save_title": "Confirm Enable Saving",
        "msg_enable_save_text": "This will create a folder in your device to save contents, confirm?",
        "btn_yes": "Yes",
        "btn_no": "No",
        "msg_name_taken_title": "Name Exists",
        "msg_name_taken_text": "The name '{}' is already taken.\n\nDo you want to add a unique suffix (e.g., _2) to rename it anyway?",
        # Temp Cleaner
        "dlg_temp_title": "Temporary File Manager",
        "lbl_temp_info": "Temp file path: {}\nOnly one item should appear here per program run\nDelete if the number of programs and items do not match (means that there are redundant trash temporary files)",
        "btn_refresh": "Refresh",
        "btn_del_sel": "Delete Selected",
        "msg_no_temp": "No temporary cache folders found",
        "status_running": "[RUNNING]",
        "status_unknown": "Unknown Date",
        "msg_confirm_del_title": "Confirm Delete",
        "msg_confirm_del_text": "Delete {} temporary folders?",
        "btn_view_temp": "View Temporary Files",
        "tip_view_temp": "Manage the cache files\nNormally they are removed when program exits, no need to remove manually",
        "menu_rename": "Rename",
        "menu_delete": "Delete",
        "msg_rename_title": "Rename Blueprint",
        "msg_rename_label": "New Name:",
        "msg_rename_exists": "A blueprint with this name already exists.",
        "msg_confirm_del_bp": "Are you sure you want to delete blueprint '{}'?\nThis cannot be undone",
        "btn_view_templates": "View Saved Templates",
        "dlg_tpl_title": "Template Manager",
        "lbl_sort": "Sort By:",
        "sort_alpha": "Alphabetical (A-Z)",
        "sort_newest": "Newest First",
        "sort_oldest": "Oldest First",
        "msg_confirm_del_tpl": "Delete {} selected templates?",
        "menu_duplicate": "Duplicate",
        "msg_dup_err": "Failed to duplicate blueprint: {}",
        "lbl_node_type": "Type:",
        "tip_open_save_folder": "Right click to open folder",
        "lbl_ai_setting": "AI Settings",
        "lbl_ai_title": "AI Assistant",
        "ph_chat": "AI responses will appear here...",
        "btn_send": "Send",
        "lbl_ai_config_win": "AI Configuration",
        "lbl_api": "API url:",
        "lbl_api_key": "API key:",
        "lbl_model": "Model:",
        "lbl_ready": "Ready",
        "lbl_think": "Thinking...",
        "ph_enter": "Enter here...",
        "tlp_clear_history": "Clear history, you will use more and more tokens as the conversation continues"
    },
    
    "CN": {
        "window_title": "UE5 蓝图查看器",
        "btn_show": "当前蓝图",
        "btn_mode_simple": "简化文本",
        "btn_mode_raw": "原始文本",
        "btn_sort": "自动排序",
        "chk_coords": "节点坐标",
        "tip_coords": "如果选中,<当前蓝图>里的<简化文本>将包含坐标",
        "btn_spec": "格式规范(AI提示词)",
        "btn_copy1":"复制",
        "btn_copy2":"已复制!",
        "search_placeholder": "搜索...",
        "spec_text": SPEC_CN,
        # Dialog: Edit Node
        "dlg_edit_title": "编辑节点",
        "lbl_node_name": "节点名称:",
        "lbl_inputs": "输入引脚(英文分号隔开):",
        "lbl_outputs": "输出引脚(英文分号隔开):",
        "btn_ok": "确定",
        "btn_cancel": "取消",
        "btn_delete": "删除节点",
        "msg_del_title": "确认删除",
        "msg_del_text": "是否确定删除此节点?",
        # Dialog: Paste
        "dlg_paste_title": "粘贴蓝图文本",
        "dlg_paste_holder": "在此粘贴...",
        "import_template":"导入节点模板",
        # Dialog: Show
        "dlg_show_title": "当前蓝图文本",
        "tip_no_raw": "原始文本不可用",
        "tip_has_raw":"原始文本可用",
        "dlg_spec_title": "格式规范(AI提示词)",
        # Dialog: Errors
        "msg_err_title": "错误",
        "msg_conv_err": "无法转换原始 UE 数据: ",
        "msg_parse_err": "无法解析文件: ",
        # Setting
        "btn_setting": "设置",
        "dlg_setting_title": "设置",
        "chk_enable_save": "启用保存功能",
        "tip_enable_save": "为本程序创建文件夹<NodeUE>,内包含配置文件,模板和蓝图\n取消勾选时将删除此文件夹及其内含的文件,若不想删除模板和蓝图,请更改保存路径或手动保存备份",
        "btn_update_path": "更改保存路径",
        "tip_update_path": "更改保存文件的保存路径\n当前文件会被迁移(配置文件除外),不会留下垃圾文件\n若想删除配置文件,请使用<删除配置文件>按钮",
        "btn_del_config": "删除配置文件",
        "tip_del_config": "删除偏好设置文件,程序将忘记自定义路径",
        "lbl_setting_instr": "程序将生成模板文件并在启动时加载\n拖拽/粘贴原始文本时,新节点类型将自动合并",
        "msg_del_config_title": "删除配置",
        "msg_del_config_text": "这将重置所有偏好设置",
        "msg_disable_save_title": "禁用保存",
        "msg_disable_save_text": "取消选中将删除整个<NodeUE>文件夹,若内含有模板或蓝图将被一并删除\n无法恢复,确认?",
        "msg_copy_err": "复制的内容包含没有原始文本的节点!",
        "msg_import_stat": "检测到{}个节点类型; {}个重复类型; 新增{}个类型; 总计{}个类型",
        "msg_tpl_missing": "无法找到模板文件: {}",
        "msg_path_updated": "模板路径已更新",
        "msg_config_deleted": "配置已删除，重启程序以重置",
        "msg_tpl_loaded": "已加载模板: {}",
        "msg_pasted": "已粘贴 {} 个节点",
        "lbl_curr_path": "当前路径: {}",
        # BP savings
        "btn_open_bp": "打开蓝图",
        "btn_save_bp": "保存蓝图",
        "dlg_open_bp_title": "打开已保存蓝图",
        "lbl_open_bp": "选择要打开的蓝图:",
        "dlg_save_bp_title": "保存蓝图",
        "lbl_save_bp": "输入蓝图名称:",
        "msg_bp_saved": "蓝图保存成功!",
        "msg_bp_exists": "蓝图 '{}' 已存在。是否覆盖?",
        "msg_bp_err": "保存/加载蓝图时出错: {}",
        "msg_no_bp": "未找到已保存的蓝图",
        "msg_enable_save_title": "确认启用保存",
        "msg_enable_save_text": "这将在您的设备上创建一个文件夹以保存内容，确认吗？",
        "btn_yes": "是",
        "btn_no": "否",
        "msg_name_taken_title": "名称已存在",
        "msg_name_taken_text": "名称 '{}' 已被占用。\n\n您是否要添加唯一后缀 (如 _2) 进行重命名？",
        # Temp Cleaner
        "dlg_temp_title": "临时文件管理器",
        "lbl_temp_info": "临时缓存文件夹: {}\n每运行一个程序对应一个临时文件\n若临时文件与程序数量不对应,请删除冗余的临时文件(可能存在垃圾文件)",
        "btn_refresh": "刷新",
        "btn_del_sel": "删除选中项",
        "msg_no_temp": "未找到临时缓存文件夹",
        "status_running": "[运行中]",
        "status_unknown": "未知日期",
        "msg_confirm_del_title": "确认删除",
        "msg_confirm_del_text": "删除 {} 个临时文件夹？",
        "btn_view_temp": "查看临时文件",
        "tip_view_temp": "管理缓存文件\n一般情况下程序结束运行时将自动删除,无需手动删除",
        "menu_rename": "重命名",
        "menu_delete": "删除",
        "msg_rename_title": "重命名蓝图",
        "msg_rename_label": "新名称:",
        "msg_rename_exists": "该名称的蓝图已存在。",
        "msg_confirm_del_bp": "确定要删除蓝图 '{}' 吗？\n此操作无法撤销",
        "btn_view_templates": "查看保存的模板",
        "dlg_tpl_title": "模板管理器",
        "lbl_sort": "排序方式:",
        "sort_alpha": "按字母 (A-Z)",
        "sort_newest": "最新保存",
        "sort_oldest": "最早保存",
        "msg_confirm_del_tpl": "确定删除选中的 {} 个模板?",
        "menu_duplicate": "创建副本",
        "msg_dup_err": "复制蓝图失败: {}",
        "lbl_node_type": "类型:",
        "tip_open_save_folder": "右键进入文件夹",
        "lbl_ai_setting": "AI设置",
        "lbl_ai_title": "AI助手",
        "ph_chat": "AI在这里回复...",
        "btn_send": "发送",
        "lbl_ai_config_win": "AI配置",
        "lbl_api": "API 地址:",
        "lbl_api_key": "API 密钥:",
        "lbl_model": "模型:",
        "lbl_ready": "已就绪",
        "lbl_think": "思考中...",
        "ph_enter": "在此输入...",
        "tlp_clear_history": "清空历史,当对话越来越长的时候,每一次问答用的token会越来越多"
    }
}

# Global State
CURRENT_LANG = "EN"

def T(key):
    """Helper to get current language string"""
    return TRANSLATIONS[CURRENT_LANG].get(key, key)

def ask_confirmation(parent, title, text):
    """Helper to show a localized Yes/No confirmation dialog."""
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    btn_yes = msg.addButton(T("btn_yes"), QMessageBox.ButtonRole.YesRole)
    btn_no = msg.addButton(T("btn_no"), QMessageBox.ButtonRole.NoRole)
    msg.exec()
    return msg.clickedButton() == btn_yes

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for Nuitka """
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ClickableLabel(QLabel):
    clicked = Signal() 
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

# ==========================================
#        INTEGRATED T3D PARSING LOGIC
# ==========================================
def clean_and_humanize(name):
    # 1. Specific UI Renames (Keep these, but remove spaces from the result)
    if name == "GetObjectClass": return "GetClass"
    if name == "GetTransform": return "GetActorTransform"
    if name == "SpawnActorFromClass": return "SpawnActor"
    if name == "GetHitResultUnderCursorByChannel": return "GetHitResultUnderCursorByChannel"
    
    # --- MATH LIBRARY RENAMES (Remove spaces from overrides) ---
    if name == "FClamp": return "Clamp(Float)"
    if name == "Clamp": return "Clamp(Integer)"
    if name == "ClampInt64": return "Clamp(Integer64)"
    
    if name == "FMax": return "Max(Float)"
    if name == "FMin": return "Min(Float)"
    if name == "Max": return "Max(Integer)"
    if name == "Min": return "Min(Integer)"
    
    if name == "FAbs": return "Abs(Float)"
    if name == "Abs": return "Abs(Integer)"
    # ---------------------------

    # 2. Standard Cleanup (Remove prefixes)
    for p in ["K2Node_", "K2_", "Array_", "On_", "Conv_"]:
        if name.startswith(p): name = name[len(p):]
    
    # 3. Handle "Receive" -> "Event"
    if name.startswith("Receive"):
        name = "Event" + name[7:]

    # [MODIFIED] Do NOT split CamelCase. 
    # Previously: name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    # We just strip whitespace/underscores now to enforce strict CamelCase.
    return name.replace("_", "").replace(" ", "").strip()

def parse_ue_color(val_str):
    """
    Detects (R=x,G=y,B=z,A=w) and returns 'R,G,B' string 0-255
    """
    if "R=" in val_str and "G=" in val_str and "B=" in val_str:
        try:
            # Extract numbers using regex
            import re
            m_r = re.search(r'R=([\d\.]+)', val_str)
            m_g = re.search(r'G=([\d\.]+)', val_str)
            m_b = re.search(r'B=([\d\.]+)', val_str)
            
            if m_r and m_g and m_b:
                r = int(float(m_r.group(1)) * 255)
                g = int(float(m_g.group(1)) * 255)
                b = int(float(m_b.group(1)) * 255)
                return f"{r},{g},{b}"
        except Exception as e:
            print(f"Failed to parse color: {e}")
    return None

def clean_value(pin_name, raw_val):
    """
    Maps internal default values to UI values (Fixes Errors 1 & 7)
    """

    if raw_val == "TraceTypeQuery1": return "Visibility"
    if raw_val == "TraceTypeQuery2": return "Camera"
    if raw_val == "AlwaysSpawn": return "Always Spawn, Ignore Collisions"
    if raw_val == "MultiplyWithRoot": return "Multiply Scale with Root Component Scale"
    if raw_val == "Undefined": return "Default"
    
    # Other common cleanups
    if raw_val == "True": return "True"
    if raw_val == "False": return "False"
    if raw_val.lower() == "true": return "True"
    if raw_val.lower() == "false": return "False"
        
    return raw_val

def get_pin_ui_name(raw_pin_name, pin_line):
    """
    Extracts the true UI name of a pin. 
    Now separates 'Exec' into 'inExec' and 'outExec'.
    """
    # --- STRATEGY 1: Check PinFriendlyName (The "Golden Source") ---
    
    # A. Complex Split Pins
    if "INVTEXT" in pin_line:
        inv_texts = re.findall(r'INVTEXT\("([^"]+)"\)', pin_line)
        if inv_texts:
            return " ".join(inv_texts)

    # B. NSLOCTEXT (Check this BEFORE simple match to avoid partial matches)
    # Allow flexible spacing around commas
    ns_match = re.search(r'NSLOCTEXT\(\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)', pin_line)
    if ns_match:
        val = ns_match.group(1)
        if val.lower() == "true": return "True"
        if val.lower() == "false": return "False"
        return val

    # C. Simple Friendly Names
    simple_match = re.search(r'PinFriendlyName="([^"]+)"', pin_line)
    if simple_match:
        name = simple_match.group(1)
        # Only use it if it doesn't look like a function call (e.g. NSLOCTEXT) that failed to match above
        if "(" not in name and name.lower() not in ["execute", "then", "exec"]:
            return name.replace(" ", "")
        
    # --- STRATEGY 2: Clean the Internal Name ---
    name = raw_pin_name
    
    if name.startswith("then_") and name[5:].isdigit():
        return f"Then {name[5:]}"

    if name.startswith("b") and len(name) > 1 and name[1].isupper():
        name = name[1:]
        
    name = name.replace("_", "")
    
    # --- NEW: Strict Exec Naming ---
    low_name = name.lower()
    
    # 1. Standard Input Exec
    if low_name == "execute": 
        return "inExec"
    
    # 2. Standard Output Exec
    if low_name == "then": 
        return "outExec"
    
    # 3. Ambiguous "Exec" (Check Direction)
    if low_name == "exec":
        # Check if the T3D line defines it as an Output
        if 'Direction="EGPD_Output"' in pin_line:
            return "outExec"
        return "inExec"
    
    return name.strip()

def universal_get_node_name(raw_text):
    # Strict Class Detection
    class_match = re.search(r'Begin Object Class=[\w\./]+\.([^ "\']+)', raw_text)
    node_class = class_match.group(1) if class_match else ""
    
    final_name = "Unknown" # Placeholder

    # --- BLOCK 1: High Priority Overrides ---
    if "K2Node_CallParentFunction" in node_class:
        func_match = re.search(r'MemberName="([^"]+)"', raw_text)
        if func_match:
            final_name = f"Parent: {clean_and_humanize(func_match.group(1))}"
        else:
            final_name = "Parent Call"
            
    elif "K2Node_FunctionResult" in node_class:
        final_name = "Return Node"

    elif "K2Node_InputKey" in node_class:
        key_match = re.search(r'InputKey=([a-zA-Z0-9_]+)', raw_text)
        if key_match:
            key_name = key_match.group(1)
            digit_map = { "Zero": "0", "One": "1", "Two": "2", "Three": "3", "Four": "4", "Five": "5", "Six": "6", "Seven": "7", "Eight": "8", "Nine": "9" }
            final_name = digit_map.get(key_name, key_name)
        else:
            final_name = "Input Key"

    # --- BLOCK 2: Standard Extraction ---
    else:
        # Prefix Logic
        prefix = ""
        if "K2Node_BreakStruct" in node_class:      prefix = "Break"
        elif "K2Node_MakeStruct" in node_class:     prefix = "Make"
        elif "K2Node_GetSubsystem" in node_class:   prefix = "Get"
        elif "K2Node_AddComponent" in node_class:   prefix = "Add"
        elif "K2Node_VariableGet" in node_class:    prefix = "Get"
        elif "K2Node_VariableSet" in node_class:    prefix = "Set"
        
        # Name Extraction Logic
        raw_name = None
        
        # Try Bind/Delegate
        if "K2Node_AssignDelegate" in node_class:
            del_match = re.search(r'DelegateReference=.*?MemberName="([^"]+)"', raw_text)
            if del_match: raw_name = f"BindEventTo{clean_and_humanize(del_match.group(1))}"
            else: prefix = "BindEventTo"
        
        # Try Custom Event / Event
        elif "K2Node_CustomEvent" in node_class:
            cust_match = re.search(r'CustomFunctionName="([^"]+)"', raw_text)
            if cust_match: raw_name = cust_match.group(1)
        elif "K2Node_Event" in node_class:
            event_match = re.search(r'EventReference=.*?MemberName="([^"]+)"', raw_text)
            if event_match:
                raw_event = event_match.group(1)
                event_map = { "ReceiveBeginPlay": "EventBeginPlay", "ReceiveTick": "EventTick", "ReceiveAnyDamage": "EventAnyDamage", "ReceiveDestroyed": "EventDestroyed" }
                raw_name = event_map.get(raw_event, raw_event)
                if raw_name.startswith("Receive"): raw_name = "Event" + raw_name[7:]
        
        # Try Cast
        elif not raw_name:
             target_match = re.search(r'TargetType=.*\.([^"\'\s]+)[\'"]', raw_text)
             if target_match:
                cls_name = target_match.group(1)
                if cls_name.endswith("_C"): cls_name = cls_name[:-2]
                raw_name = f"CastTo{clean_and_humanize(cls_name)}"

        # Try Function Reference
        if not raw_name:
            func_match = re.search(r'FunctionReference=\(.*?MemberName="([^"]+)"', raw_text)
            member_parent_match = re.search(r'MemberParent="([^"]+)"', raw_text)
            if func_match:
                func_name = func_match.group(1)
                parent_path = member_parent_match.group(1) if member_parent_match else ""
                if func_name == "GetTransform" and ("Engine.Actor" in parent_path or "Engine.SceneComponent" in parent_path):
                     raw_name = "GetActorTransform"
                elif func_name == "GetObjectClass": 
                     raw_name = "GetClass"
                else:
                     raw_name = func_name

        # Fallback Scans
        if not raw_name:
            simple_keys = [
                r'MacroGraph=.*?\'([^\']+)\'', r'InputAction=.*\.([^"\']+)\'', 
                r'Enum=.*\.([^"\']+)\'', r'CustomClass=.*\.([^"\']+)\'', 
                r'OperationName="([^"]+)"'
            ]
            for p in simple_keys:
                m = re.search(p, raw_text)
                if m: 
                    raw_name = m.group(1).split(':')[-1] # Handle Macro:Name
                    break

        if not raw_name:
            overrides = { "K2Node_IfThenElse": "Branch", "K2Node_ExecutionSequence": "Sequence", "K2Node_MultiGate": "MultiGate", "K2Node_Knot": "RerouteNode" }
            raw_name = overrides.get(node_class, node_class)

        # Apply Cleanup
        symbol_map = {"EqualEqual": "Equal", "NotEqual": "NotEqual", "Add": "Add", "Subtract": "Subtract"}
        if raw_name in symbol_map: raw_name = symbol_map[raw_name]

        final_name = clean_and_humanize(raw_name)
        
        # [MODIFIED] Combine Prefix without space
        if prefix and not final_name.startswith(prefix):
            final_name = f"{prefix}{final_name}"

    # --- BLOCK 3: Context Injection (The Fix) ---
    context = get_context_suffix(raw_text)
    if context:
        if context.startswith("Default__"): context = context[9:]
        # [MODIFIED] Check without spaces
        if context.lower() not in final_name.lower():
             # We keep the space ONLY before the parenthesis for readability in the UI context suffix
             # OR remove it if you want "PrintString(Context)"
             final_name = f"{final_name}({context})" 
             
    return final_name

def parse_pin_text(text):
    custom_color = None
    clean_text = text
    
    # Extract color tag <R,G,B>
    color_match = re.search(r'<(\d+),(\d+),(\d+)>', text)
    if color_match:
        r, g, b = int(color_match.group(1)), int(color_match.group(2)), int(color_match.group(3))
        custom_color = QColor(r, g, b)
        clean_text = text.replace(color_match.group(0), "")

    # Extract Value \(Value\)
    match = re.match(r"^(.*?)\\\((.*)\\\)$", clean_text)
    if match:
        return match.group(1).strip(), match.group(2).strip(), True, custom_color
        
    return clean_text, "", False, custom_color

def update_raw_block_value(raw_block, target_ui_label, new_value, is_input):
    """Updates the DefaultValue in a raw T3D block for a specific pin."""
    lines = raw_block.split('\n')
    new_lines = []
    found_and_replaced = False
    
    safe_val = new_value.replace('"', '\\"')
    
    for line in lines:
        if "CustomProperties Pin" in line:
            name_match = re.search(r'PinName="([^"]+)"', line)
            if name_match:
                raw_name = name_match.group(1)
                
                # Check Direction
                is_line_output = 'Direction="EGPD_Output"' in line
                if is_input and is_line_output:
                    new_lines.append(line)
                    continue
                if not is_input and not is_line_output:
                    new_lines.append(line)
                    continue

                # Check Name Match
                ui_name = get_pin_ui_name(raw_name, line)
                
                if ui_name == target_ui_label:
                    # Found Pin! Update DefaultValue
                    if re.search(r'\bDefaultValue="', line):
                        # [FIX] Regex handles replacing values that contain escaped quotes
                        line = re.sub(r'\bDefaultValue="((?:[^"\\]|\\.)*)"', f'DefaultValue="{safe_val}"', line)
                        found_and_replaced = True
                    else:
                        # Append if missing
                        stripped = line.rstrip()
                        if stripped.endswith(",)"):
                            line = stripped[:-2] + f',DefaultValue="{safe_val}",)'
                            found_and_replaced = True
                        elif stripped.endswith(")"):
                            line = stripped[:-1] + f',DefaultValue="{safe_val}")'
                            found_and_replaced = True
                            
        new_lines.append(line)
        
    if found_and_replaced:
        return "\n".join(new_lines)
    return None

def get_context_suffix(raw_text):
    """
    Extracts the source context (Class or Macro Library) to disambiguate nodes.
    Handles 'MemberParent', 'MacroGraph', and 'TargetType'.
    """
    # 1. Check for Function Calls (MemberParent)
    # Search for MemberParent="..."
    # We capture everything inside the quotes.
    func_match = re.search(r'MemberParent="([^"]+)"', raw_text)
    if func_match:
        full_path = func_match.group(1)
        # Typical path: /Script/CoreUObject.Class'/Script/Engine.KismetSystemLibrary'
        # We want the last part after the dot, but before the closing quote if it exists.
        
        # Split by dot
        parts = full_path.split('.')
        if parts:
            cls_name = parts[-1]
            # Strip trailing single quote if present
            if cls_name.endswith("'"): 
                cls_name = cls_name[:-1]
            
            # Clean up common suffixes/prefixes
            if cls_name.endswith("_C"): cls_name = cls_name[:-2]
            if cls_name.startswith("Default__"): cls_name = cls_name[9:]
            
            # Filter out generic 'Object' context which isn't helpful
            if cls_name != "Object":
                return cls_name

    # 2. Check for Macros (MacroGraph)
    # Ex: MacroGraph=".../StandardMacros.StandardMacros:IsValid"
    macro_match = re.search(r'MacroGraph="([^"]+)"', raw_text)
    if macro_match:
        full_path = macro_match.group(1)
        # Extract the part before the colon :IsValid
        if ":" in full_path:
            path_part = full_path.split(':')[0]
            # Get the name after the last dot
            lib_name = path_part.split('.')[-1]
            return lib_name

    # 3. Check for specific Target Types (TargetType)
    target_match = re.search(r'TargetType=.*\.([^"\'\s]+)', raw_text)
    if target_match:
        t_name = target_match.group(1)
        if t_name.endswith("_C"): t_name = t_name[:-2]
        return t_name

    return ""

def get_node_data(raw_text):
    # 1. Get Node ID & Name
    id_match = re.search(r'Name="([^"]+)"', raw_text)
    node_id = id_match.group(1) if id_match else "Unknown"
    
    base_name = universal_get_node_name(raw_text)

    # Position Extraction
    x_match = re.search(r'NodePosX=(-?\d+)', raw_text)
    y_match = re.search(r'NodePosY=(-?\d+)', raw_text)
    pos_x = int(x_match.group(1)) if x_match else 0
    pos_y = int(y_match.group(1)) if y_match else 0

    # 2. Parse Pins (CRITICAL FIX: Line-by-Line processing)
    pins = []
    lines = raw_text.split('\n')
    is_set_var = "K2Node_VariableSet" in raw_text

    for line in lines:
        line = line.strip()
        
        # Only look at lines defining CustomProperties Pin
        if not line.startswith("CustomProperties Pin"):
            continue

        # Check Hidden (Now reliable because we have the full line)
        if "bHidden=True" in line: continue

        # Extract Pin ID
        guid_match = re.search(r'PinId=([A-F0-9]+)', line, re.IGNORECASE)
        pin_guid = guid_match.group(1) if guid_match else ""

        # Internal Name
        name_match = re.search(r'PinName="([^"]+)"', line)
        internal_name = name_match.group(1) if name_match else "Unk"

        # Apply Pin Name Fixes
        p_name = get_pin_ui_name(internal_name, line)

        # Handle Set Variable special case
        if is_set_var and internal_name == "Output_Get": 
            p_name = "" 

        # Direction
        d_match = re.search(r'Direction="([^"]+)"', line)
        direction = "OUT" if (d_match and "Output" in d_match.group(1)) else "IN"
        
        cat_match = re.search(r'PinType\.PinCategory="([^"]+)"', line)
        pin_category = cat_match.group(1) if cat_match else ""

        # Value Extraction
        val_str = ""
        
        # Use \b to avoid matching AutogeneratedDefaultValue
        val_match = re.search(r'\bDefaultValue="((?:[^"\\]|\\.)*)"', line)
        
        if val_match:
            raw_val = val_match.group(1).replace('\\"', '"')
            val_str = clean_value(p_name, raw_val)
        elif 'DefaultObject="' in line:
             obj_match = re.search(r'DefaultObject=".*\.([^"\']+)"', line)
             if obj_match: val_str = obj_match.group(1)
        if direction == "IN" and pin_category == "bool" and not val_str:
            val_str = "False"
        rgb_color = parse_ue_color(val_str)
        if rgb_color:
            p_name = f"{p_name}<{rgb_color}>"

        if p_name == "CollisionHandlingOverride" and val_str == "Undefined":
            val_str = "Default"
        elif p_name == "TransformScaleMethod" and val_str == "MultiplyWithRoot":
            val_str = "MultiplyScaleWithRootComponentScale"

        # Links
        links = []
        link_match = re.search(r'LinkedTo=\(([^)]+)\)', line)
        if link_match:
            entries = link_match.group(1).split(',')
            for e in entries:
                parts = e.strip().split()
                if len(parts) >= 2:
                    links.append({"node": parts[0], "pin_guid": parts[1]})

        # Self Pin Logic
        if direction == "IN" and not val_str and not links and internal_name == "self":
            val_str = "self"

        pins.append({
            "guid": pin_guid,
            "name": p_name,
            "dir": direction,
            "value": val_str,
            "links": links,
            "category": pin_category
        })

    data = { "id": node_id, "type": base_name, "x": pos_x, "y": pos_y, "pins": pins }
    data["raw_text"] = raw_text
    return data

def trace_signal(target_id, target_pin_guid, all_nodes_map):
    
    target_node = all_nodes_map.get(target_id)
    if not target_node: return []

    if target_node['type'] != "RerouteNode":
        return [{"node": target_id, "pin_guid": target_pin_guid}]

    resolved_targets = []
    for pin in target_node['pins']:
        if pin['dir'] == "OUT" and pin['links']:
            for link in pin['links']:
                sub_results = trace_signal(link['node'], link['pin_guid'], all_nodes_map)
                resolved_targets.extend(sub_results)
    
    return resolved_targets

def generate_spec_file(raw_input):
    node_blocks = re.findall(r'Begin Object.*?End Object', raw_input, re.DOTALL)
    parsed_nodes = []
    nodes_map = {}
    pin_lookup = {}

    for block in node_blocks:
        if "Class=/Script/UnrealEd.EdGraphNode_Comment" in block: continue
        data = get_node_data(block)
        parsed_nodes.append(data)
        nodes_map[data['id']] = data
        pin_lookup[data['id']] = {}
        for p in data['pins']:
            pin_lookup[data['id']][p['guid']] = p['name']

    name_counts = {}
    id_map = {}
    extracted_positions = {}
    raw_data_map = {}
    internal_name_map = {}
    
    for node in parsed_nodes:
        t_name = node['type']
        if t_name == "RerouteNode": continue 

        if t_name not in name_counts: name_counts[t_name] = 1
        else: name_counts[t_name] += 1
        
        unique_name = f"{t_name}_{name_counts[t_name]}"
        id_map[node['id']] = unique_name
        node['unique_name'] = unique_name
        
        # Store the position
        extracted_positions[unique_name] = (node['x'], node['y'])
        if 'raw_text' in node:
            raw_data_map[unique_name] = node['raw_text']
        internal_name_map[unique_name] = node['id']

    output_lines = []
    output_lines.append("# Node Definitions")

    for node in parsed_nodes:
        if node['type'] == "RerouteNode": continue

        in_pins = []
        out_pins = []
        for p in node['pins']:
            p_str = p['name']
            if p['dir'] == "IN" and p['value'] and not p['links']:
                val = p['value']
                if val.startswith('('):
                    p_str = p['name']
                else:
                    p_str = f"{p['name']}\\({val}\\)"
            
            if p['dir'] == "IN": in_pins.append(p_str)
            else: out_pins.append(p_str)

        line = f"{node['unique_name']} ({'; '.join(in_pins)}) : ({'; '.join(out_pins)})"
        output_lines.append(line)

    output_lines.append("\n# Links")

    for node in parsed_nodes:
        if node['type'] == "RerouteNode": continue
        src_name = node['unique_name']
        
        for p in node['pins']:
            if p['dir'] != "OUT": continue 
            if not p['links']: continue

            for link in p['links']:
                resolved_targets = trace_signal(link['node'], link['pin_guid'], nodes_map)

                for target in resolved_targets:
                    tgt_id = target['node']
                    tgt_guid = target['pin_guid']
                    
                    if tgt_id in id_map:
                        tgt_name = id_map[tgt_id]
                        tgt_pin_name = "UnknownPin"
                        if tgt_id in pin_lookup and tgt_guid in pin_lookup[tgt_id]:
                            tgt_pin_name = pin_lookup[tgt_id][tgt_guid]
                        
                        l_line = f"{src_name} ({p['name']}) -> {tgt_name} ({tgt_pin_name})"
                        output_lines.append(l_line)

    # Return Tuple: (Spec Text, Dictionary of Positions)
    return "\n".join(output_lines), extracted_positions, raw_data_map, internal_name_map

# --------------------------------------------------------------------- #
# CONFIGURATION
# --------------------------------------------------------------------- #

DEFAULT_NODE_WIDTH = 220 
HEADER_HEIGHT = 30
PIN_ROW_HEIGHT = 24
FONT_SIZE = 10
SORT_X_GAP = 380
SORT_Y_GAP = 200

# Colors
C_BACKGROUND = QColor(26, 26, 26)
C_GRID_LIGHT = QColor(40, 40, 40)
C_GRID_DARK = QColor(35, 35, 35)
C_NODE_BODY = QColor(15, 15, 15, 200)
C_NODE_BORDER = QColor(0, 0, 0)
C_NODE_HEADER = QColor(40, 80, 120) 
C_NODE_HEADER_GRAD = QColor(60, 110, 160)
C_PIN_TEXT = QColor(220, 220, 220)
C_VALUE_TEXT = QColor(180, 180, 180) 
C_VALUE_BG = QColor(30, 30, 30)      
C_LINK = QColor(255, 255, 255)
C_RESIZE_HANDLE = QColor(200, 200, 200, 150)

EXEC_NAMES = [
    "Exec", "inExec", "outExec", "InputExec", "Output", "OutputExec", 
    "Then", "Completed", "True", "False", "Loop Body", "Reset",
    "Pressed", "Released", "OnClicked", "Update", "Finished", "CastFailed",
    "Is Valid", "Is Not Valid", "Started", "Ongoing", "Canceled", "Triggered",
    "Row Found", "Row Not Found", "Break", "On Success", "On Failure", "Cast Failed"
]
def is_exec_name(name):
    """Checks if a pin name matches any EXEC_NAME, ignoring spaces."""
    if not name: return False
    # Remove spaces from the input name
    normalized_input = name.replace(" ", "")
    
    # Check against space-stripped versions of the EXEC_NAMES list
    for exec_ref in EXEC_NAMES:
        if exec_ref.replace(" ", "") == normalized_input:
            return True
    return False
# --------------------------------------------------------------------- #
# DARK THEME STYLESHEET
# --------------------------------------------------------------------- #
DARK_STYLESHEET = """
    /* Main Window and Dialog Backgrounds */
    QMainWindow, QDialog, QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-family: "Microsoft YaHei UI";
    }

    /* Buttons */
    QPushButton {
        background-color: #333333;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px 12px;
        min-width: 60px;
    }
    QPushButton:hover {
        background-color: #444444;
        border: 1px solid #666666;
    }
    QPushButton:pressed {
        background-color: #222222;
        border: 1px solid #444444;
    }
    QPushButton:disabled {
        background-color: #2a2a2a;
        color: #707070;
        border: 1px solid #3a3a3a;
    }

    /* Input Fields (Line Edit, Text Edit) */
    QLineEdit, QTextEdit {
        background-color: #252525;
        color: #ffffff;
        border: 1px solid #3e3e3e;
        border-radius: 3px;
        padding: 4px;
        selection-background-color: #0078d7;
    }
    QLineEdit:focus, QTextEdit:focus {
        border: 1px solid #0078d7;
    }

    /* Scrollbars (Vertical) */
    QScrollBar:vertical {
        border: none;
        background: #1e1e1e;
        width: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: #444444;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #555555;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    /* Scrollbars (Horizontal) */
    QScrollBar:horizontal {
        border: none;
        background: #1e1e1e;
        height: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:horizontal {
        background: #444444;
        min-width: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #555555;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }

    /* Message Boxes */
    QMessageBox {
        background-color: #1e1e1e;
    }
    QLabel {
        color: #e0e0e0;
    }
"""

# ==========================================
#        CONFIG MANAGER
# ==========================================
class ConfigManager:
    def __init__(self):
        self.app_name = "NodeUE"
        self.default_folder = self._get_default_path()
        self.config_path = os.path.join(self.default_folder, "Config.json")
        self.default_template_path = os.path.join(self.default_folder, "Templates.json")
        
        # In ConfigManager.__init__
        self.data = {
            "enable_saving": False,
            "language": "EN",
            "template_path": self.default_template_path,
            "show_coords": False,
            # --- NEW: AI Settings ---
            "ai_url": "https://api.deepseek.com/chat/completions",
            "ai_model": "deepseek-chat",
            "ai_key": "",
            "ai_unlocked": True
        }
        self.load()

    def _get_default_path(self):
        system = platform.system()
        if system == "Windows":
            # Uses LOCALAPPDATA environment variable
            # Falls back to APPDATA if LOCAL isn't found
            base_path = os.environ.get('LOCALAPPDATA', os.environ['APPDATA'])
            return os.path.join(base_path, self.app_name)
        elif system == "Darwin": # Mac
            return os.path.join(os.path.expanduser("~/Library/Application Support"), self.app_name)
        else: # Linux/Unix
            return os.path.join(os.path.expanduser("~/.config"), self.app_name)

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save(self):
        if not self.data["enable_saving"]: return
        if not os.path.exists(self.default_folder):
            os.makedirs(self.default_folder, exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Config Save Failed: {e}")

    def delete_config(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
    
    def delete_all_data(self):
        # Remove the whole folder
        if os.path.exists(self.default_folder):
            shutil.rmtree(self.default_folder)

CONFIG = ConfigManager()

# --------------------------------------------------------------------- #
# DIALOGS
# --------------------------------------------------------------------- #

class OpenBlueprintDialog(QDialog):
    def __init__(self, parent=None, blueprint_list=[]):
        super().__init__(parent)
        self.parent_ref = parent # Store reference to main app to access helper methods
        self.setWindowTitle(T("dlg_open_bp_title"))
        self.resize(600, 500)
        self.selected_blueprint = None

        layout = QVBoxLayout(self)
        
        lbl = QLabel(T("lbl_open_bp"))
        layout.addWidget(lbl)
        
        # --- List Widget ---
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(80, 80))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setGridSize(QSize(100, 120))
        self.list_widget.setSpacing(10)
        
        # Enable Context Menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # Populate
        self.refresh_items(blueprint_list)

        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.list_widget)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(T("btn_ok"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(T("btn_cancel"))
        btns.accepted.connect(self.accept_selection)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def create_blueprint_icon(self):
        # [Use the exact same icon generation code from your previous version]
        # Copy the previous create_blueprint_icon method here...
        # For brevity in this snippet, I assume you keep the existing method logic.
        icon_size = 128 
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(QColor(0, 0, 0, 0)) 
        painter = QPainter(pixmap)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        font = QFont("Arial Black", 32, QFont.Weight.Bold)
        white_color = QColor(255, 255, 255)
        shadow_color_start = QColor(120, 120, 120) 
        shadow_color_end = QColor(60, 60, 60)
        transform = QTransform()
        transform.translate(icon_size / 2, icon_size / 2)
        transform.rotate(30)
        transform.shear(-0.1, 0.0)
        transform.translate(-10, 5) 
        painter.setTransform(transform)
        
        def draw_faux_3d_text(p, text, pos_y, is_hollow):
            path = QPainterPath()
            font_metrics = QFontMetricsF(font)
            text_width = font_metrics.horizontalAdvance(text)
            baseline_offset = font_metrics.ascent() / 2 
            path.addText(QPointF(-text_width / 2, pos_y + baseline_offset), font, text)
            for i in range(8, -1, -1):
                dx, dy = i * 0.5, i * 0.8
                p.save()
                p.translate(dx, dy)
                if i == 0:
                    if is_hollow:
                        pen = QPen(white_color, 6.0); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
                    else:
                        p.setPen(Qt.PenStyle.NoPen); p.setBrush(white_color); p.drawPath(path)
                else:
                    ratio = i / 8
                    r = shadow_color_start.red() * (1-ratio) + shadow_color_end.red() * ratio
                    g = shadow_color_start.green() * (1-ratio) + shadow_color_end.green() * ratio
                    b = shadow_color_start.blue() * (1-ratio) + shadow_color_end.blue() * ratio
                    layer_color = QColor(int(r), int(g), int(b))
                    if is_hollow:
                        pen = QPen(layer_color, 6.0); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
                    else:
                        p.setPen(Qt.PenStyle.NoPen); p.setBrush(layer_color)
                        stroker = QPainterPathStroker(); stroker.setWidth(2); stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        shadow_path = stroker.createStroke(path).united(path)
                        p.drawPath(shadow_path)
                p.restore()

        draw_faux_3d_text(painter, "    UE", 10 + 5, True)
        draw_faux_3d_text(painter, "  Node", -20, False)
        painter.end()
        return QIcon(pixmap)

    def refresh_items(self, names):
        self.list_widget.clear()
        icon = self.create_blueprint_icon()
        for name in names:
            item = QListWidgetItem(icon, name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.list_widget.addItem(item)

    def show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        
        action_rename = menu.addAction(T("menu_rename"))
        action_duplicate = menu.addAction(T("menu_duplicate")) # <--- Added
        action_delete = menu.addAction(T("menu_delete"))
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        
        if action == action_rename:
            self.perform_rename(item)
        elif action == action_duplicate:
            self.perform_duplicate(item) # <--- Connect
        elif action == action_delete:
            self.perform_delete(item)

    def perform_duplicate(self, item):
        old_name = item.text()
        root_dir = self.parent_ref.get_blueprints_dir()
        
        # 1. Determine New Name (Increment Suffix)
        base_name = old_name
        counter = 2
        
        # Check if it already ends in _N
        match = re.search(r'^(.*)_(\d+)$', old_name)
        if match:
            base_name = match.group(1)
            counter = int(match.group(2)) + 1
            
        new_name = f"{base_name}_{counter}"
        new_path = os.path.join(root_dir, new_name)
        
        # Keep incrementing if file exists
        while os.path.exists(new_path):
            counter += 1
            new_name = f"{base_name}_{counter}"
            new_path = os.path.join(root_dir, new_name)
            
        # 2. Perform Copy
        old_path = os.path.join(root_dir, old_name)
        try:
            # Copy the entire folder
            shutil.copytree(old_path, new_path)
            
            # 3. Rename the internal JSON file to match the new folder name
            # (Blueprints expect FolderName/FolderName.json)
            old_json = os.path.join(new_path, f"{old_name}.json")
            new_json = os.path.join(new_path, f"{new_name}.json")
            
            if os.path.exists(old_json):
                os.rename(old_json, new_json)
                
            # 4. Add to List
            # Use the same icon as the source item
            new_item = QListWidgetItem(item.icon(), new_name)
            new_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self.list_widget.addItem(new_item)
            
        except Exception as e:
            QMessageBox.critical(self, T("msg_err_title"), T("msg_dup_err").format(e))

    def perform_rename(self, item):
        old_name = item.text()
        new_name, ok = QInputDialog.getText(self, T("msg_rename_title"), T("msg_rename_label"), text=old_name)
        
        if ok and new_name and new_name != old_name:
            new_name = re.sub(r'[\\/*?:"<>|]', "", new_name.strip()) # Sanitize
            root_dir = self.parent_ref.get_blueprints_dir()
            
            old_path = os.path.join(root_dir, old_name)
            new_path = os.path.join(root_dir, new_name)
            
            if os.path.exists(new_path):
                QMessageBox.warning(self, T("msg_err_title"), T("msg_rename_exists"))
                return
                
            try:
                # 1. Rename Folder
                os.rename(old_path, new_path)
                
                # 2. Rename JSON inside
                old_json = os.path.join(new_path, f"{old_name}.json")
                new_json = os.path.join(new_path, f"{new_name}.json")
                if os.path.exists(old_json):
                    os.rename(old_json, new_json)
                    
                item.setText(new_name)
                
            except Exception as e:
                QMessageBox.critical(self, T("msg_err_title"), str(e))

    def perform_delete(self, item):
        name = item.text()
        if ask_confirmation(self, T("msg_del_title"), T("msg_confirm_del_bp").format(name)):
            root_dir = self.parent_ref.get_blueprints_dir()
            bp_path = os.path.join(root_dir, name)
            try:
                shutil.rmtree(bp_path)
                # Remove from List
                row = self.list_widget.row(item)
                self.list_widget.takeItem(row)
            except Exception as e:
                QMessageBox.critical(self, T("msg_err_title"), str(e))

    def accept_selection(self):
        if self.list_widget.currentItem():
            self.selected_blueprint = self.list_widget.currentItem().text()
            self.accept()

class NodeEditorDialog(QDialog):
    def __init__(self, parent=None, name="", inputs=[], outputs=[]):
        super().__init__(parent)
        self.setWindowTitle(T("dlg_edit_title"))
        self.resize(700, 280)
        self.delete_requested = False 
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Form
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow(T("lbl_node_name"), self.name_edit)
        
        in_str = "".join([f"{x};" for x in inputs])
        self.ins_edit = QLineEdit(in_str)
        form.addRow(T("lbl_inputs"), self.ins_edit)
        
        out_str = "".join([f"{x};" for x in outputs])
        self.outs_edit = QLineEdit(out_str)
        form.addRow(T("lbl_outputs"), self.outs_edit)
        
        main_layout.addLayout(form)
        main_layout.addStretch()
        
        # OK / Cancel row
        ok_btn = QPushButton(T("btn_ok"))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton(T("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        ok_cancel_layout = QHBoxLayout()
        ok_cancel_layout.addStretch()
        ok_cancel_layout.addWidget(ok_btn)
        ok_cancel_layout.addWidget(cancel_btn)
        ok_cancel_layout.addStretch()
        
        main_layout.addLayout(ok_cancel_layout)
        
        # Delete button
        self.btn_delete = QPushButton(T("btn_delete"))
        self.btn_delete.setStyleSheet("""
            background-color: #8B0000;
            color: white;
            font-weight: bold;
            padding: 10px;
            border-radius: 4px;
            font-size: 10pt;
        """)
        self.btn_delete.clicked.connect(self.request_delete)
        main_layout.addWidget(self.btn_delete)
        
    def request_delete(self):
        if ask_confirmation(self, T("msg_del_title"), T("msg_del_text")):
            self.delete_requested = True
            self.accept()
        
    def get_data(self):
        name = self.name_edit.text().strip()
        
        raw_ins = self.ins_edit.text()
        ins = []
        if raw_ins:
            # Logic: Split by semi, then remove the inevitable empty string at the end
            tokens = [x.strip() for x in raw_ins.split(';')]
            if tokens and tokens[-1] == "":
                tokens.pop()
            ins = tokens

        raw_outs = self.outs_edit.text()
        outs = []
        if raw_outs:
            tokens = [x.strip() for x in raw_outs.split(';')]
            if tokens and tokens[-1] == "":
                tokens.pop()
            outs = tokens

        return name, ins, outs

class TempCleanerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("dlg_temp_title"))
        self.resize(600, 400)
        
        # This MUST match the folder name defined in the Nuitka command
        self.target_folder_name = "NodeUE_Runtime" 
        self.temp_root = os.path.join(tempfile.gettempdir(), self.target_folder_name)
        
        layout = QVBoxLayout(self)
        
        # Info Label (Formatted with path)
        lbl_info = QLabel(T("lbl_temp_info").format(self.temp_root))
        lbl_info.setStyleSheet("color: #AAAAAA; margin-bottom: 10px;")
        layout.addWidget(lbl_info)
        
        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton(T("btn_refresh"))
        self.btn_refresh.clicked.connect(self.scan_files)
        
        self.btn_delete = QPushButton(T("btn_del_sel"))
        self.btn_delete.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_selected)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)
        
        self.current_run_path = os.path.dirname(os.path.abspath(__file__))
        self.scan_files()

    def scan_files(self):
        self.list_widget.clear()
        if not os.path.exists(self.temp_root):
            item = QListWidgetItem(T("msg_no_temp"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return

        # Get current Process ID
        current_pid = str(os.getpid())

        # List directories in the specific parent folder
        try:
            subdirs = [d for d in os.listdir(self.temp_root) 
                       if os.path.isdir(os.path.join(self.temp_root, d))]
            
            for d in subdirs:
                full_path = os.path.join(self.temp_root, d)
                
                # Get Stats
                try:
                    ctime = os.path.getctime(full_path)
                    date_str = datetime.datetime.fromtimestamp(ctime).strftime('%Y-%m-%d %H:%M:%S')
                    size_mb = self.get_size_mb(full_path)
                    display_text = f"{date_str}  -  {d}  ({size_mb:.2f} MB)"
                except Exception as e:
                    print(f"Failed to read temp directory stats for {d}: {e}")
                    display_text = f"{T('status_unknown')}  -  {d}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                
                is_current = False
                
                # Check 1: Does folder name end with underscore + PID? (Standard Nuitka Spec)
                if d.endswith(f"_{current_pid}"):
                    is_current = True
                
                # Check 2: Fallback Path check (just in case)
                elif os.path.normcase(full_path) == os.path.normcase(self.current_run_path):
                    is_current = True

                if is_current:
                    item.setText(f"{T('status_running')} {display_text}")
                    # Green text to verify it's detected, or stick to Gray
                    item.setForeground(QColor(150, 150, 150)) 
                    item.setFlags(Qt.ItemFlag.NoItemFlags) # Disable selection
                
                self.list_widget.addItem(item)
                
        except Exception as e:
            print(f"Scan error: {e}")

    def get_size_mb(self, path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)

    def delete_selected(self):
        items = self.list_widget.selectedItems()
        if not items: return
        
        # Use localized confirmation dialog
        if not ask_confirmation(self, T("msg_confirm_del_title"), T("msg_confirm_del_text").format(len(items))):
            return
            
        for item in items:
            path = item.data(Qt.ItemDataRole.UserRole)
            try:
                shutil.rmtree(path)
            except Exception as e:
                os.system(f'rmdir /S /Q "{path}"')
        
        self.scan_files()

class TemplateManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent.parent_app if parent else None
        self.setWindowTitle(T("dlg_tpl_title"))
        self.resize(600, 600) 
        
        layout = QVBoxLayout(self)
        
        # Sort Controls
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(T("lbl_sort")))
        
        self.combo_sort = QComboBox()
        self.combo_sort.addItems([T("sort_alpha"), T("sort_newest"), T("sort_oldest")])
        self.combo_sort.currentIndexChanged.connect(self.refresh_list)
        top_layout.addWidget(self.combo_sort)
        top_layout.addStretch()

        # Search Box
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(T("search_placeholder"))
        self.txt_search.setFixedWidth(200) 
        self.txt_search.setClearButtonEnabled(True) 
        self.txt_search.textChanged.connect(self.on_search_text_changed)
        top_layout.addWidget(self.txt_search)

        layout.addLayout(top_layout)
        
        # Tree Widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setColumnCount(2)
        self.tree_widget.setHeaderLabels([T("lbl_node_name"), T("lbl_node_type")]) 
        header = self.tree_widget.headerItem()
        header.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter) 
        header.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter) 
        self.tree_widget.setRootIsDecorated(False) 
        self.tree_widget.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.tree_widget)
        
        # --- Buttons Area (Modified) ---
        btn_layout = QHBoxLayout()
        
        # Delete Button
        self.btn_delete = QPushButton(T("btn_del_sel"))
        self.btn_delete.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_selected)
        
        # Export Button (Replaced OK button)
        export_text = "Export txt" if CURRENT_LANG == "EN" else "导出txt"
        self.btn_export = QPushButton(export_text)
        self.btn_export.setToolTip("Export all templates to a text file for UE5")
        self.btn_export.clicked.connect(self.export_all_templates)

        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_export) # Added Export button
        layout.addLayout(btn_layout)
        
        self.refresh_list()
    
    def on_search_text_changed(self, text):
        search_term = text.lower().replace(" ", "")
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            raw_name = item.text(0)
            clean_name = raw_name.lower().replace(" ", "")
            is_match = search_term in clean_name
            item.setHidden(not is_match)

    def refresh_list(self):
        if not self.parent_app: return
        self.tree_widget.clear()
        
        keys = list(self.parent_app.raw_node_templates.keys())
        idx = self.combo_sort.currentIndex()
        if idx == 0: 
            keys.sort(key=lambda k: k.lower())
        elif idx == 1: 
            keys.reverse()
        
        for k in keys:
            if "::" in k:
                display_text, node_type = k.split("::", 1)
            else:
                display_text, node_type = k, "Unknown"

            item = QTreeWidgetItem([display_text, node_type])
            item.setData(0, Qt.ItemDataRole.UserRole, k) 
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            self.tree_widget.addTopLevelItem(item)

    def delete_selected(self):
        items = self.tree_widget.selectedItems()
        if not items: return
        
        if not ask_confirmation(self, T("msg_confirm_del_title"), T("msg_confirm_del_tpl").format(len(items))):
            return
            
        for item in items:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key in self.parent_app.raw_node_templates:
                del self.parent_app.raw_node_templates[key]
        
        self.parent_app.save_templates_to_disk()
        self.refresh_list()

    def export_all_templates(self):
        """Exports all raw T3D templates to a single text file."""
        if not self.parent_app or not self.parent_app.raw_node_templates:
            return

        # 1. Combine all raw text
        all_content = "\n\n".join(self.parent_app.raw_node_templates.values())

        # 2. Define default filename based on language
        default_filename = "Template.txt" if CURRENT_LANG == "EN" else "模板.txt"
        
        # 3. Open Save Dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            self.btn_export.text(), 
            default_filename, 
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(all_content)
                
                msg = f"Successfully exported {len(self.parent_app.raw_node_templates)} templates."
                QMessageBox.information(self, "Export Successful", msg)
                self.accept() # Close dialog after successful export
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

class SettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.setWindowTitle(T("dlg_setting_title"))
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Enable Checkbox
        self.chk_enable = QCheckBox(T("chk_enable_save"))
        self.chk_enable.setToolTip(T("tip_enable_save"))
        self.chk_enable.setChecked(CONFIG.data["enable_saving"])
        self.chk_enable.toggled.connect(self.on_toggle_enable)
        layout.addWidget(self.chk_enable)
        
        # Instruction
        lbl_instr = QLabel(T("lbl_setting_instr"))
        lbl_instr.setWordWrap(True)
        lbl_instr.setStyleSheet("color: #AAAAAA; font-size: 9pt;")
        layout.addWidget(lbl_instr)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # AI
        self.btn_ai_config = QPushButton(T("lbl_ai_setting")) # New Button
        self.btn_ai_config.clicked.connect(self.open_ai_settings)
        layout.addWidget(self.btn_ai_config)
        # Hide the button if not unlocked
        self.btn_ai_config.setVisible(CONFIG.data.get("ai_unlocked", False))

        # Buttons Area
        self.btn_update = QPushButton(T("btn_update_path"))
        self.btn_update.setToolTip(T("tip_update_path") + "\n" + T("tip_open_save_folder"))
        self.btn_update.clicked.connect(self.update_path)
        self.btn_update.installEventFilter(self)
        layout.addWidget(self.btn_update)

        # Extract folder path
        current_dir = os.path.dirname(CONFIG.data["template_path"])
        self.lbl_path = QLabel(T("lbl_curr_path").format(current_dir))
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet("color: #888888; font-size: 9pt; margin-bottom: 5px;")
        layout.addWidget(self.lbl_path)

        self.btn_templates = QPushButton(T("btn_view_templates"))
        self.btn_templates.clicked.connect(self.open_template_manager)
        layout.addWidget(self.btn_templates)
        
        self.btn_temp = QPushButton(T("btn_view_temp"))
        self.btn_temp.setToolTip(T("tip_view_temp"))
        self.btn_temp.clicked.connect(self.open_temp_manager)
        layout.addWidget(self.btn_temp)

        self.btn_del = QPushButton(T("btn_del_config"))
        self.btn_del.setToolTip(T("tip_del_config"))
        self.btn_del.setStyleSheet("background-color: #552222;")
        self.btn_del.clicked.connect(self.delete_config)
        layout.addWidget(self.btn_del)

        layout.addStretch()
        self.refresh_state()

    def open_ai_settings(self):
        dlg = AISettingDialog(self)
        dlg.exec()

    def eventFilter(self, source, event):
        if source == self.btn_update and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                self.open_current_folder()
                return True
        return super().eventFilter(source, event)

    def open_current_folder(self):
        """Opens the current template folder in the OS File Explorer"""
        path = CONFIG.data["template_path"]
        folder = os.path.dirname(path)
        
        # Ensure folder exists
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
    
    def open_template_manager(self):
        dlg = TemplateManagerDialog(self)
        dlg.exec()

    def open_temp_manager(self):
        dlg = TempCleanerDialog(self)
        dlg.exec()

    def refresh_state(self):
        enabled = self.chk_enable.isChecked()
        self.btn_update.setEnabled(enabled)
        self.btn_del.setEnabled(enabled)

    def on_toggle_enable(self, checked):
        if checked:
            # Enable Confirmation
            if not ask_confirmation(self, T("msg_enable_save_title"), T("msg_enable_save_text")):
                # User Cancelled
                self.chk_enable.blockSignals(True)
                self.chk_enable.setChecked(False)
                self.chk_enable.blockSignals(False)
                return
            
            # Logic
            CONFIG.data["enable_saving"] = True
            CONFIG.save()
            self.parent_app.save_templates_to_disk()
            self.refresh_state()
        else:
            # Disable Confirmation
            if ask_confirmation(self, T("msg_disable_save_title"), T("msg_disable_save_text")):
                # Logic
                CONFIG.data["enable_saving"] = False
                CONFIG.delete_all_data()
                self.refresh_state()
            else:
                # User Cancelled
                self.chk_enable.blockSignals(True)
                self.chk_enable.setChecked(True) 
                self.chk_enable.blockSignals(False)

    def update_path(self):
        # 1. Get current info
        current_path = CONFIG.data["template_path"]
        old_dir = os.path.dirname(current_path)
        current_filename = os.path.basename(current_path)

        # Default to current dir for the dialog
        start_dir = old_dir if os.path.exists(old_dir) else ""
            
        # 2. Select NEW FOLDER
        folder = QFileDialog.getExistingDirectory(self, T("btn_update_path"), start_dir)
        
        if folder:
            # Construct new full path using the EXISTING filename
            new_path = os.path.join(folder, current_filename)
            new_dir = folder
            
            # Check if we are actually changing location
            if new_path != current_path:
                # A. Move the Template File
                if os.path.exists(current_path):
                    try:
                        shutil.move(current_path, new_path)
                    except Exception as e:
                        print(f"Move template failed: {e}")
                
                # B. Move Blueprint Folders
                # We scan the OLD directory for folders that look like blueprints
                if os.path.exists(old_dir):
                    try:
                        for entry_name in os.listdir(old_dir):
                            old_entry_path = os.path.join(old_dir, entry_name)
                            
                            # Check if it is a directory
                            if os.path.isdir(old_entry_path):
                                # Check if it is a blueprint (must contain Name.json)
                                bp_json = os.path.join(old_entry_path, f"{entry_name}.json")
                                
                                if os.path.exists(bp_json):
                                    new_entry_path = os.path.join(new_dir, entry_name)
                                    # Move the folder
                                    # Note: shutil.move might fail if destination exists, so we try/catch
                                    try:
                                        shutil.move(old_entry_path, new_entry_path)
                                    except Exception as move_err:
                                        print(f"Skipped moving {entry_name}: {move_err}")
                                        
                    except Exception as e:
                        print(f"Scanning blueprints failed: {e}")
            
                # C. Save Config & Update UI
                CONFIG.data["template_path"] = new_path
                CONFIG.save()
                self.parent_app.show_flash_message(T("msg_path_updated"))
                self.lbl_path.setText(T("lbl_curr_path").format(new_dir))

    def delete_config(self):
        if ask_confirmation(self, T("msg_del_config_title"), T("msg_del_config_text")):
            CONFIG.delete_config()
            self.parent_app.show_flash_message(T("msg_config_deleted"))
            self.close()

class DirectPasteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("dlg_paste_title"))
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(T("dlg_paste_holder"))
        self.text_edit.setStyleSheet("background-color: #202020; color: #FFFFFF; font-family: Microsoft YaHei UI, monospace;")
        layout.addWidget(self.text_edit)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(T("btn_ok"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(T("btn_cancel"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_text(self):
        return self.text_edit.toPlainText()

class SpecDialog(QDialog):
    """A simple read-only dialog for displaying the Spec/Instructions."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("dlg_spec_title"))
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        # Set a monospaced font for better readability of the spec
        self.text_edit.setFont(QFont("Microsoft YaHei UI", 10))
        layout.addWidget(self.text_edit)
        
        # --- Modified Button Section ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch() # Pushes the button to the right
        
        self.btn_copy = QPushButton(T("btn_copy1"))
        self.btn_copy.setMinimumWidth(100)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        
        btn_layout.addWidget(self.btn_copy)
        layout.addLayout(btn_layout)

    def copy_to_clipboard(self):
        """Copies text to clipboard and updates button text."""
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self.btn_copy.setText(T("btn_copy2"))
        self.btn_copy.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;") # Change to Green

class ShowGraphDialog(QDialog):
    def __init__(self, simplified_text, raw_text_func, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("dlg_show_title"))
        self.resize(800, 600)
        self.simplified_text = simplified_text
        self.get_raw_text = raw_text_func 
        self.current_mode = "SIMPLE"

        layout = QVBoxLayout(self)
        
        # --- Toolbar ---
        toolbar = QHBoxLayout()
        
        self.btn_simple = QPushButton(T("btn_mode_simple"))
        self.btn_simple.setCheckable(True)
        self.btn_simple.setChecked(True)
        self.btn_simple.clicked.connect(lambda: self.switch_mode("SIMPLE"))
        
        self.btn_raw = QPushButton(T("btn_mode_raw"))
        self.btn_raw.setCheckable(True)
        self.btn_raw.clicked.connect(lambda: self.switch_mode("RAW"))
        
        toolbar.addWidget(self.btn_simple)
        toolbar.addWidget(self.btn_raw)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # --- Text Area ---
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(False) 
        self.text_edit.setStyleSheet("background-color: #202020; color: #FFFFFF; font-family: Microsoft YaHei UI, monospace;")
        layout.addWidget(self.text_edit)
        
        # --- Copy Button Section (Modified) ---
        btn_layout = QHBoxLayout()

        self.btn_open_bp = QPushButton(T("btn_open_bp"))
        self.btn_open_bp.clicked.connect(self.on_open_bp)
        
        self.btn_save_bp = QPushButton(T("btn_save_bp"))
        self.btn_save_bp.clicked.connect(self.on_save_bp)
        
        # Only show if saving is enabled
        is_saving_enabled = CONFIG.data["enable_saving"]
        self.btn_open_bp.setVisible(is_saving_enabled)
        self.btn_save_bp.setVisible(is_saving_enabled)
        
        btn_layout.addWidget(self.btn_open_bp)
        btn_layout.addWidget(self.btn_save_bp)

        btn_layout.addStretch() 
        
        self.btn_copy = QPushButton(T("btn_copy1")) # "Copy"
        self.btn_copy.setMinimumWidth(100)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        
        btn_layout.addWidget(self.btn_copy)
        layout.addLayout(btn_layout)
        
        self.update_text()
    
    def on_open_bp(self):
        self.parent().open_saved_blueprint()
        self.close()

    def on_save_bp(self):
        if self.parent().save_current_blueprint():
            self.close()

    def switch_mode(self, mode):
        self.current_mode = mode
        self.btn_simple.setChecked(mode == "SIMPLE")
        self.btn_raw.setChecked(mode == "RAW")
        self.update_text()
        # Reset button text when switching modes
        self.btn_copy.setText(T("btn_copy1"))
        self.btn_copy.setStyleSheet("")

    def update_text(self):
        if self.current_mode == "SIMPLE":
            self.text_edit.setPlainText(self.simplified_text)
        else:
            self.text_edit.setPlainText(self.get_raw_text())

    def copy_to_clipboard(self):
        """Copies text to clipboard and updates button text."""
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self.btn_copy.setText(T("btn_copy2")) # "Copied!"
        self.btn_copy.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")

# --------------------------------------------------------------------- #
# DATA CLASSES
# --------------------------------------------------------------------- #

class NodeData:
    def __init__(self, name):
        self.name = name
        self.internal_name = name
        self.raw_text = ""
        self.exec_in_pins = []   
        self.exec_out_pins = []  
        self.data_inputs = [] 
        self.data_outputs = []
        self.connected_inputs = set()
        self.connected_outputs = set()
        self.x = 0
        self.y = 0

    def clear_pins(self):
        self.exec_in_pins = []
        self.exec_out_pins = []
        self.data_inputs = []
        self.data_outputs = []

    def is_exec_node(self):
        return bool(self.exec_in_pins or self.exec_out_pins)

    def add_input(self, pin_name):
        # Check if it is a numbered "Then" pin (e.g. "Then 1")
        is_seq_pin = (pin_name.startswith("Then ") and pin_name[5:].isdigit())
        
        # FIX: Allow duplicates/empty pins (Removed 'if pin_name not in...' check)
        if is_exec_name(pin_name) or is_seq_pin:
            self.exec_in_pins.append(pin_name)
        else:
            self.data_inputs.append(pin_name)
    
    def add_output(self, pin_name):
        is_seq_pin = (pin_name.startswith("Then ") and pin_name[5:].isdigit())
        
        # FIX: Allow duplicates/empty pins
        if is_exec_name(pin_name) or is_seq_pin:
            self.exec_out_pins.append(pin_name)
        else:
            self.data_outputs.append(pin_name)

class LinkData:
    def __init__(self, src_node, src_pin, dst_node, dst_pin):
        self.src_node = src_node
        self.src_pin = src_pin
        self.dst_node = dst_node
        self.dst_pin = dst_pin

# --------------------------------------------------------------------- #
# GRAPHICS ITEMS
# --------------------------------------------------------------------- #
class UENodeItem(QGraphicsObject):
    positionChanged = Signal(object)

    def __init__(self, node_data, app):
        super().__init__()
        self.node_data = node_data
        self.app = app
        self.setAcceptHoverEvents(True)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(node_data.x, node_data.y)
        self.setZValue(10)
        
        self.is_reroute = "RerouteNode" in self.node_data.name

        if self.node_data.is_exec_node():
             self.math_symbol, self.math_color = (None, None)
        else:
             self.math_symbol, self.math_color = self._get_math_details(self.node_data.name)

        self.is_compact = bool(self.math_symbol)
        self.is_highlighted = False # For Search
        self.is_error = False
        self.min_height = 0
        self.error_timer = QTimer()
        self.error_timer.setSingleShot(True)
        self.error_timer.timeout.connect(self.hide_error)
        self.min_width = DEFAULT_NODE_WIDTH
        self.calculate_layout()
        
        self._resizing = False
        self._resize_start_pos = None
        self._resize_start_size = None
        
        self._editing_index = -1
        self._editing_is_input = False
        self._editing_label = "" 
        self.editor = None
        self.proxy = None

    def try_update_raw_text_value(self, raw_block, target_ui_label, new_value, is_input):
        """
        scans the raw_block for the pin corresponding to target_ui_label.
        If found, replaces its DefaultValue="..." with new_value.
        Returns the modified block string, or None if failed.
        """
        lines = raw_block.split('\n')
        new_lines = []
        found_and_replaced = False
        
        # Prepare safe value (escape quotes)
        safe_val = new_value.replace('"', '\\"')
        
        for line in lines:
            if "CustomProperties Pin" in line:
                # 1. Parse Internal Name
                name_match = re.search(r'PinName="([^"]+)"', line)
                if name_match:
                    raw_name = name_match.group(1)
                    
                    # 2. Check Direction
                    # If editing input, we ignore lines that say "Output"
                    # If editing output, we ignore lines that DO NOT say "Output" (implied Input)
                    is_line_output = 'Direction="EGPD_Output"' in line
                    if is_input and is_line_output:
                        new_lines.append(line)
                        continue
                    if not is_input and not is_line_output:
                        new_lines.append(line)
                        continue

                    # 3. Resolve to UI Name to compare with what user edited
                    # (We assume get_pin_ui_name is available globally or imported)
                    ui_name = get_pin_ui_name(raw_name, line)
                    
                    if ui_name == target_ui_label:
                        
                        # [FIX] STRICT CHECK: Use \b to verify if the REAL DefaultValue exists
                        if re.search(r'\bDefaultValue="', line):
                            # [FIX] Use \b to replace ONLY the real DefaultValue
                            line = re.sub(r'\bDefaultValue="([^"]*)"', f'DefaultValue="{safe_val}"', line)
                            found_and_replaced = True
                        else:
                            # DefaultValue missing (or only Autogenerated exists), append it
                            stripped = line.rstrip()
                            if stripped.endswith(",)"):
                                line = stripped[:-2] + f',DefaultValue="{safe_val}",)'
                                found_and_replaced = True
                            elif stripped.endswith(")"):
                                line = stripped[:-1] + f',DefaultValue="{safe_val}")'
                                found_and_replaced = True
                                
            new_lines.append(line)
            
        if found_and_replaced:
            return "\n".join(new_lines)
        return None

    def trigger_error(self):
        """Shows the red frame and starts the 5s timer."""
        self.is_error = True
        self.update()
        self.error_timer.start(5000) # 5 seconds

    def hide_error(self):
        """Hides the red frame."""
        self.is_error = False
        self.update()

    def _get_status_icon_rect(self):
        """Returns the hit-box for the status icon (Warning or Success)."""
        # If it's a Reroute (Knot) or Compact Math node, we don't show any icon.
        if self.is_reroute or self.is_compact: 
            return QRectF() 
        # Otherwise, always reserve space at the top-left
        return QRectF(8, 5, 20, 20)

    def hoverMoveEvent(self, event):
        # 1. Check Status Icon Hover
        icon_rect = self._get_status_icon_rect()
        if not icon_rect.isEmpty() and icon_rect.contains(event.pos()):
            if not self.node_data.raw_text:
                self.setToolTip(T("tip_no_raw"))
            else:
                self.setToolTip(T("tip_has_raw"))
            super().hoverMoveEvent(event)
            return

        # 2. Check Value Box Hover (Existing Logic)
        hit = self.get_hit_value_box(event.pos())
        if hit:
            _, _, pin_text, _ = hit
            _, val, _, _ = self.parse_pin(pin_text)
            self.setToolTip(val)
        else:
            self.setToolTip("")
        super().hoverMoveEvent(event)

    def _get_math_details(self, name):
        clean = re.sub(r'_\d+$', '', name).replace(" ", "")
        c_green = QColor(108, 168, 108)

        def is_pure_math(n):
            non_math_words = [
                "To", "From", "At", "Into",
                "Component", "Actor", "Child", "Item", "Widget", 
                "Instance", "Element", "Mapping", "Tag", "Socket",
                "Screen", "Viewport", "Class", "Name", "Local", "Resource"
            ]
            for word in non_math_words:
                if word in n: return False
            return True

        if clean.startswith("Add") and is_pure_math(clean): return ("+", c_green)
        if clean.startswith("Subtract") and is_pure_math(clean): return ("-", c_green)
        if clean.startswith("Multiply") and is_pure_math(clean): return ("×", c_green)
        if clean.startswith("Divide") and is_pure_math(clean): return ("÷", c_green)
        
        if clean.startswith("EqualEqual") or clean.startswith("Equal"): return ("==", c_green)
        if clean.startswith("NotEqual"): return ("!=", c_green)
        if clean.startswith("LessEqual"): return ("<=", c_green)
        if clean.startswith("GreaterEqual"): return (">=", c_green)
        if clean.startswith("Less"): return ("<", c_green)
        if clean.startswith("Greater"): return (">", c_green)
        
        if clean.startswith("And"): return ("AND", c_green)
        if clean.startswith("Or"): return ("OR", c_green)
        if clean.startswith("Not"): return ("NOT", c_green)
        
        return (None, None)

    def _get_header_color(self, node_name_clean):
        # --- NEW: Strip Parentheses for color matching ---
        # "Is Valid (StandardMacros)" -> "Is Valid"
        base_name_for_color = re.sub(r'\s*\(.*?\)', '', node_name_clean).strip()
        
        has_pressed = "Pressed" in self.node_data.exec_out_pins
        has_released = "Released" in self.node_data.exec_out_pins
        
        if (has_pressed and has_released):
             base = QColor(130, 0, 0)
             return base, base.lighter(130)

        has_delegate = False
        for p in self.node_data.data_outputs:
            if self._is_delegate(p):
                has_delegate = True
                break

        if has_delegate or \
           node_name_clean.startswith("Event") or \
           node_name_clean.startswith("On") or \
           node_name_clean.startswith("Receive") or \
           node_name_clean.startswith("InputKey") or \
           node_name_clean.startswith("InputAction"):
            base = QColor(130, 0, 0)
            return base, base.lighter(130)

        flow_nodes = [
            "Branch", "Sequence", "DoOnce", "DoN", "FlipFlop", 
            "ForLoop", "WhileLoop", "Gate", "MultiGate", 
            "Delay", "RetriggerableDelay", "Switch", "Select", "Valid", "Is Valid"
        ]
        
        # Check specific Flow list OR if "Macro" is in the full name
        # Note: We use the FULL name for the "Macro" check so "Is Valid (StandardMacros)" turns Grey
        if base_name_for_color in flow_nodes or "Macro" in node_name_clean:
            base = QColor(110, 110, 110)
            return base, base.lighter(130)

        if node_name_clean.startswith("CastTo"):
            base = QColor(46, 104, 109)
            return base, base.lighter(130)

        if node_name_clean.startswith("Set ") or node_name_clean.startswith("Get "):
             base = QColor(0, 100, 90) 
             return base, base.lighter(130)

        base = QColor(68, 107, 183)
        return base, base.lighter(130)

    def _is_delegate(self, pin_text):
        return "OutputDelegate" in pin_text.replace(" ", "")

    def _get_value_box_rect(self, current_y):
        if self.is_reroute: return QRectF()
        max_w = 65 if self.is_compact else 65
        box_width = min(self.width - 40, max_w)
        return QRectF(25, current_y, box_width, 20)

    def force_close_editor(self):
        if self.editor and self._editing_index != -1:
            self.finish_editing_value(self._editing_index, self._editing_is_input, self._editing_label)

    def start_editing_value(self, index, is_input, full_text, rect):
        self.force_close_editor()
        label, value, _, _ = self.parse_pin(full_text)
        self._editing_index = index
        self._editing_is_input = is_input
        self._editing_label = label

        self.editor = QLineEdit(value)
        self.editor.setFont(QFont("Microsoft YaHei UI", 8, QFont.Weight.Medium))
        self.editor.setStyleSheet("""
            QLineEdit { 
                background-color: rgba(30, 30, 30, 128); 
                color: #FFFFFF; 
                border: 1px solid #00AAFF; 
                border-radius: 4px;
            }
        """)
        
        self.proxy = QGraphicsProxyWidget(self)
        self.proxy.setWidget(self.editor)
        self.proxy.setGeometry(rect)
        self.proxy.setZValue(100) 
        self.editor.setFocus()
        self.editor.selectAll()
        self.editor.editingFinished.connect(lambda: self.finish_editing_value(index, is_input, label))

    def update_editor_geometry(self):
        if not self.proxy or not self.editor or self._editing_index == -1:
            return

        start_y = 10 if self.is_compact else (HEADER_HEIGHT + (PIN_ROW_HEIGHT / 2))
        current_y = start_y
        
        target_list = self.node_data.data_inputs if self._editing_is_input else self.node_data.data_outputs
        exec_list = self.node_data.exec_in_pins if self._editing_is_input else self.node_data.exec_out_pins
        
        current_y += len(exec_list) * PIN_ROW_HEIGHT

        found_rect = None
        for i, pin_text in enumerate(target_list):
            if not self._editing_is_input and self._is_delegate(pin_text): continue
            _, _, has_val, _ = self.parse_pin(pin_text)
            
            if has_val:
                if i == self._editing_index:
                    val_y = current_y + PIN_ROW_HEIGHT
                    found_rect = self._get_value_box_rect(val_y - 10)
                    break
                current_y += (PIN_ROW_HEIGHT * 2)
            else:
                current_y += PIN_ROW_HEIGHT
        
        if found_rect:
            self.proxy.setGeometry(found_rect)

    def finish_editing_value(self, index, is_input, label):
        if not hasattr(self, 'editor') or not self.editor: return

        new_val = self.editor.text()
        rgb_str = parse_ue_color(new_val)
        final_label = label
        if rgb_str:
            final_label = f"{label}<{rgb_str}>"

        # Construct the full pin text with the (potentially colored) label
        new_pin_text = f"{final_label}\\({new_val}\\)"
        
        # Determine which list to modify
        target_list = self.node_data.data_inputs if is_input else self.node_data.data_outputs
        
        # [REQ 1 FIX] Check if value is actually different before doing anything
        old_pin_text = target_list[index]
        if new_pin_text == old_pin_text:
            self._cleanup_editor()
            return # EXIT EARLY: Do not touch raw_text

        # Apply the change
        target_list[index] = new_pin_text
            
        # [REQ 3 & 4 FIX] Smart Update of Raw Text
        # Instead of blindly setting raw_text = "", we try to inject the value into the existing raw_text
        if self.node_data.raw_text:
            updated_raw = update_raw_block_value(self.node_data.raw_text, label, new_val, is_input)
            
            if updated_raw:
                # SUCCESS: We updated the raw text template with the new value. Keep Green Dot.
                self.node_data.raw_text = updated_raw
            else:
                # FAILURE: Structure didn't match (e.g. complex struct split). Mark Unavailable (Yellow !).
                self.node_data.raw_text = "" 

        self._cleanup_editor()
        self.update()
        self.positionChanged.emit(self)

    def _cleanup_editor(self):
        if self.proxy:
            self.proxy.setWidget(None)
            self.scene().removeItem(self.proxy)
            self.proxy = None
        self.editor = None
        self._editing_index = -1

    def get_hit_value_box(self, local_pos):
        if self.is_reroute: return None 

        start_y = 10 if self.is_compact else (HEADER_HEIGHT + (PIN_ROW_HEIGHT / 2))
        current_y = start_y

        current_y += len(self.node_data.exec_in_pins) * PIN_ROW_HEIGHT
        for i, pin_text in enumerate(self.node_data.data_inputs):
            _, _, has_val, _ = self.parse_pin(pin_text)
            if has_val:
                val_y = current_y + PIN_ROW_HEIGHT
                box_rect = self._get_value_box_rect(val_y - 10)
                if box_rect.contains(local_pos):
                    return (i, True, pin_text, box_rect)
                current_y += (PIN_ROW_HEIGHT * 2)
            else:
                current_y += PIN_ROW_HEIGHT

        current_y = start_y
        current_y += len(self.node_data.exec_out_pins) * PIN_ROW_HEIGHT
        
        for i, pin_text in enumerate(self.node_data.data_outputs):
            if self._is_delegate(pin_text): continue
            
            _, _, has_val, _ = self.parse_pin(pin_text)
            if has_val:
                val_y = current_y + PIN_ROW_HEIGHT
                box_rect = self._get_value_box_rect(val_y - 10)
                if box_rect.contains(local_pos):
                    return (i, False, pin_text, box_rect)
                current_y += (PIN_ROW_HEIGHT * 2)
            else:
                current_y += PIN_ROW_HEIGHT
                
        return None

    def parse_pin(self, text):
        return parse_pin_text(text)

    def calculate_layout(self):
        if self.is_reroute:
            self.width = 36 
            self.height = 36
            self.min_width = 36
            self.min_height = 36
            return

        left_rows = len(self.node_data.exec_in_pins)
        for p in self.node_data.data_inputs:
            _, _, has_val, _ = self.parse_pin(p)
            left_rows += 2 if has_val else 1
            
        right_rows = len(self.node_data.exec_out_pins)
        for p in self.node_data.data_outputs:
            if self._is_delegate(p): continue
            _, _, has_val, _ = self.parse_pin(p)
            right_rows += 2 if has_val else 1

        row_count = max(1, left_rows, right_rows)
        start_y = 10 if self.is_compact else HEADER_HEIGHT
        padding = 10
        calculated_height = start_y + (row_count * PIN_ROW_HEIGHT) + padding
        
        min_h = 80 if self.is_compact else 100
        self.min_height = max(min_h, calculated_height)
        
        if not hasattr(self, 'height') or self.height < self.min_height:
            self.height = self.min_height

        base_width = 80 if self.is_compact else DEFAULT_NODE_WIDTH
        
        has_value_box = False
        for p in (self.node_data.data_inputs + self.node_data.data_outputs):
            _, _, has_val, _ = self.parse_pin(p)
            if has_val:
                has_value_box = True
                break
        
        if has_value_box:
            base_width = DEFAULT_NODE_WIDTH

        if not hasattr(self, 'width') or self.width < base_width:
            self.width = base_width

    def boundingRect(self):
        margin = 3.0 
        return QRectF(-margin, -margin, self.width + (margin * 2), self.height + (margin * 2))

    def get_pin_geometry(self, pin_name, is_input):
        if self.is_reroute:
            return self.mapToScene(self.boundingRect().center())

        if not is_input and self._is_delegate(pin_name):
            x = self.width - 15 
            y = HEADER_HEIGHT / 2
            return self.mapToScene(QPointF(x, y))

        start_y = 10 if self.is_compact else (HEADER_HEIGHT + (PIN_ROW_HEIGHT / 2))
        current_y = start_y
        x = 12 if is_input else (self.width - 12)
        
        if is_input:
            for p in self.node_data.exec_in_pins:
                if p == pin_name: return self.mapToScene(QPointF(x, current_y))
                current_y += PIN_ROW_HEIGHT
            for p in self.node_data.data_inputs:
                label, val, has_val, _ = self.parse_pin(p)
                if p == pin_name or label == pin_name: return self.mapToScene(QPointF(x, current_y))
                current_y += (PIN_ROW_HEIGHT * 2) if has_val else PIN_ROW_HEIGHT
        else:
            for p in self.node_data.exec_out_pins:
                if p == pin_name: return self.mapToScene(QPointF(x, current_y))
                current_y += PIN_ROW_HEIGHT
            for p in self.node_data.data_outputs:
                if self._is_delegate(p): continue
                label, val, has_val, _ = self.parse_pin(p)
                if p == pin_name or label == pin_name: return self.mapToScene(QPointF(x, current_y))
                current_y += (PIN_ROW_HEIGHT * 2) if has_val else PIN_ROW_HEIGHT
        
        return self.mapToScene(QPointF(x, 0)) 

    def hit_test_pin(self, pos):
        local_pos = self.mapFromScene(pos)

        if self.is_reroute:
            # --- FIX: Disable Drag-To-Link if selected ---
            if self.isSelected():
                return None
            # ---------------------------------------------

            center = QPointF(self.width/2, self.height/2)
            dx = local_pos.x() - center.x()
            dy = local_pos.y() - center.y()
            dist_sq = dx*dx + dy*dy
            if dist_sq > 100: return None 
            
            is_input_side = local_pos.x() < (self.width / 2)
            if is_input_side:
                if self.node_data.exec_in_pins: return (self.node_data.exec_in_pins[0], True)
                if self.node_data.data_inputs: return (self.parse_pin(self.node_data.data_inputs[0])[0], True)
            else:
                if self.node_data.exec_out_pins: return (self.node_data.exec_out_pins[0], False)
                if self.node_data.data_outputs: return (self.parse_pin(self.node_data.data_outputs[0])[0], False)
            return None

        for p in self.node_data.data_outputs:
            if self._is_delegate(p):
                sq_size = 20 
                sq_x = self.width - 30
                sq_y = 5
                rect = QRectF(sq_x, sq_y, sq_size, sq_size)
                if rect.contains(local_pos):
                    return (p, False)
                break

        start_y = 10 if self.is_compact else (HEADER_HEIGHT + (PIN_ROW_HEIGHT / 2))

        def check_pins(is_input):
            x_center = 12 if is_input else (self.width - 12)
            current_y = start_y
            
            p_list_exec = self.node_data.exec_in_pins if is_input else self.node_data.exec_out_pins
            for p in p_list_exec:
                dist = (QPointF(x_center, current_y) - local_pos).manhattanLength()
                if dist < 12: return p
                current_y += PIN_ROW_HEIGHT
            
            p_list_data = self.node_data.data_inputs if is_input else self.node_data.data_outputs
            for p in p_list_data:
                if not is_input and self._is_delegate(p): continue

                label, _, has_val, _ = self.parse_pin(p)
                dist = (QPointF(x_center, current_y) - local_pos).manhattanLength()
                if dist < 12: return label 
                
                current_y += (PIN_ROW_HEIGHT * 2) if has_val else PIN_ROW_HEIGHT
            return None

        pin = check_pins(True)
        if pin is not None: return (pin, True)
        
        pin = check_pins(False)
        if pin is not None: return (pin, False)
        
        return None
    
    def paint(self, painter, option, widget):
        if self.is_reroute:
            rect = self.boundingRect()
            if self.isSelected():
                painter.setPen(QPen(QColor(255, 200, 0), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(0, 0, self.width, self.height, 4, 4)
            
            center = rect.center()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(220, 220, 220)) 
            painter.drawEllipse(center, 6, 6)
            return

        path = QPainterPath()
        radius = 20 if self.is_compact else 10
        path.addRoundedRect(0, 0, self.width, self.height, radius, radius)
        
        if self.is_error:
            # Error Red Stroke
            pen = QPen(QColor(255, 0, 0), 4)
        elif self.isSelected():
            pen = QPen(QColor(255, 200, 0), 4)
        elif self.is_highlighted:
            # Highlight Green Stroke
            pen = QPen(QColor(0, 255, 0), 4) 
        else:
            pen = QPen(C_NODE_BORDER, 2)
            
        painter.setPen(pen)
        painter.setBrush(self.math_color if self.is_compact else C_NODE_BODY)
        painter.drawPath(path)

        # --- HEADER / SYMBOL ---
        if self.is_compact:
            font_size = int(min(self.width, self.height) * 0.5)
            painter.setPen(QColor(255, 255, 255, 200)) 
            sym_font = QFont("Microsoft YaHei UI", font_size, QFont.Weight.Bold)
            painter.setFont(sym_font)
            painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, self.math_symbol)
        else:
            # [MODIFIED] Strip unique ID AND context suffix (content in parens)
            full_name = self.node_data.name
            # 1. Remove _Number suffix
            base_name = re.sub(r'_\d+$', '', full_name)
            # 2. Remove (ContextString)
            display_name = re.sub(r'\s*\(.*?\)', '', base_name).strip()
            
            header_color, header_grad_color = self._get_header_color(display_name)

            header_path = QPainterPath()
            header_path.moveTo(0, HEADER_HEIGHT)
            header_path.lineTo(0, 10)
            header_path.arcTo(0, 0, 20, 20, 180, 90)
            header_path.lineTo(self.width - 10, 0)
            header_path.arcTo(self.width - 20, 0, 20, 20, 90, -90)
            header_path.lineTo(self.width, HEADER_HEIGHT)
            header_path.closeSubpath()
            
            grad = QLinearGradient(0, 0, self.width, 0)
            grad.setColorAt(0, header_color)
            grad.setColorAt(1, header_grad_color)
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(header_path)

            # --- WARNING ICON & TITLE ---
            icon_rect = self._get_status_icon_rect()
            title_padding = 10
            
            if not icon_rect.isEmpty():
                # We are drawing an icon, so shift the title to the right
                title_padding += 15 
                
                if not self.node_data.raw_text:
                    # Draw Warning (!)
                    painter.setPen(QColor(255, 215, 0)) # Gold
                    font = QFont("Microsoft YaHei UI", 12, QFont.Weight.Bold)
                    painter.setFont(font)
                    painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "!  ")
                else:
                    # Draw Success (✓)
                    painter.setPen(QColor(0, 255, 0)) # Bright Green
                    font = QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold)#, QFont.Weight.Bold
                    painter.setFont(font)
                    painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "●  ") #✓●〇

            # --- TITLE ---
            painter.setPen(Qt.GlobalColor.white)
            font = QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold)
            painter.setFont(font)
            
            # Use title_padding calculated above
            title_rect = QRectF(title_padding, 0, self.width - title_padding - 30, HEADER_HEIGHT)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, display_name)

            # Delegate Icon
            delegate_pin_name = None
            for p in self.node_data.data_outputs:
                if self._is_delegate(p):
                    delegate_pin_name = p
                    break
            
            if delegate_pin_name:
                # 1. Determine Connectivity
                label, _, _, _ = self.parse_pin(delegate_pin_name)
                is_connected = label in self.node_data.connected_outputs

                # 2. Setup Geometry
                sq_size = 12
                sq_x = self.width - 15 - (sq_size/2)
                sq_y = (HEADER_HEIGHT - sq_size) / 2
                rect = QRectF(sq_x, sq_y, sq_size, sq_size)

                # 3. Draw Filled or "Body Color" (Hollow look)
                if is_connected:
                    painter.setBrush(QColor(255, 50, 50, 255)) # Connected: Bright Red
                else:
                    painter.setBrush(C_NODE_BODY)              # Unconnected: Node Body Color
                
                painter.setPen(QPen(QColor(255, 50, 50), 2))   # Red Border
                painter.drawRoundedRect(rect, 3, 3)

        # --- PINS ---
        pin_font = QFont("Microsoft YaHei UI", 8)
        value_font = QFont("Microsoft YaHei UI", 8, QFont.Weight.Medium) 
        painter.setFont(pin_font)

        start_y = 10 if self.is_compact else (HEADER_HEIGHT + (PIN_ROW_HEIGHT / 2))
        
        input_text_rect = QRectF(25, 0, self.width - 50, 20)
        output_text_rect = QRectF(25, 0, self.width - 50, 20)

        # INPUTS
        current_y = start_y
        for pin_name in self.node_data.exec_in_pins:
            self._draw_exec_pin(painter, 12, current_y, pin_name, True)
            if not self.is_compact:
                painter.setPen(C_PIN_TEXT)
                painter.setFont(pin_font)
                r = QRectF(input_text_rect.x(), current_y - 10, input_text_rect.width(), input_text_rect.height())
                painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, pin_name)
            current_y += PIN_ROW_HEIGHT
            
        for i, pin_text in enumerate(self.node_data.data_inputs):
            label, value, has_value, custom_color = self.parse_pin(pin_text)
            
            is_connected = label in self.node_data.connected_inputs
            base_color = QColor(100, 200, 100) 
            if custom_color: base_color = custom_color
            
            if label == "Event":
                base_color = QColor(255, 50, 50) # Red
                
                if is_connected:
                    painter.setBrush(base_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                else:
                    painter.setBrush(C_NODE_BODY) 
                    painter.setPen(QPen(base_color, 2))

                # Draw Square
                sq_size = 10
                # Position square centered on x=12
                rect = QRectF(12 - (sq_size/2), current_y - (sq_size/2), sq_size, sq_size)
                painter.drawRoundedRect(rect, 2, 2)
            else:
                # Standard Circle
                if is_connected:
                    painter.setBrush(base_color)
                    painter.setPen(Qt.PenStyle.NoPen)
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(base_color, 1.5))
                
                painter.drawEllipse(QPointF(12, current_y), 5, 5)
            
            if not self.is_compact:
                if custom_color:
                    painter.setPen(custom_color)
                else:
                    painter.setPen(C_PIN_TEXT)
                painter.setFont(pin_font)
                r = QRectF(input_text_rect.x(), current_y - 10, input_text_rect.width(), input_text_rect.height())
                painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            
            if has_value:
                val_y = current_y + PIN_ROW_HEIGHT
                is_editing_this = (self._editing_index == i) and (self._editing_is_input == True)
                
                if not is_editing_this:
                    box_rect = self._get_value_box_rect(val_y - 10)
                    if self.is_compact:
                        painter.setBrush(QColor(30, 30, 30, 128))
                    else:
                        painter.setBrush(C_VALUE_BG)

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(box_rect, 4, 4)
                    
                    painter.setPen(C_VALUE_TEXT)
                    painter.setFont(value_font)
                    
                    text_rect = box_rect.adjusted(5, 0, -5, 0)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, value)
                
                current_y += (PIN_ROW_HEIGHT * 2) 
            else:
                current_y += PIN_ROW_HEIGHT

        # OUTPUTS
        current_y = start_y
        for pin_name in self.node_data.exec_out_pins:
            self._draw_exec_pin(painter, self.width - 12, current_y, pin_name, False)
            if not self.is_compact:
                painter.setPen(C_PIN_TEXT)
                painter.setFont(pin_font)
                r = QRectF(output_text_rect.x(), current_y - 10, output_text_rect.width(), output_text_rect.height())
                painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, pin_name)
            current_y += PIN_ROW_HEIGHT
            
        for i, pin_text in enumerate(self.node_data.data_outputs):
            if self._is_delegate(pin_text): continue

            label, value, has_value, custom_color = self.parse_pin(pin_text)
            
            is_connected = label in self.node_data.connected_outputs
            base_color = QColor(0, 170, 255) 
            if custom_color: base_color = custom_color
            
            if is_connected:
                painter.setBrush(base_color)
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(base_color, 1.5))
            
            painter.drawEllipse(QPointF(self.width - 12, current_y), 5, 5)
            
            if not self.is_compact:
                if custom_color:
                    painter.setPen(custom_color)
                else:
                    painter.setPen(C_PIN_TEXT)
                painter.setFont(pin_font)
                r = QRectF(output_text_rect.x(), current_y - 10, output_text_rect.width(), output_text_rect.height())
                painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, label)
            
            if has_value:
                val_y = current_y + PIN_ROW_HEIGHT
                is_editing_this = (self._editing_index == i) and (self._editing_is_input == False)

                if not is_editing_this:
                    r_val = QRectF(output_text_rect.x(), val_y - 10, output_text_rect.width(), output_text_rect.height())
                    if self.is_compact:
                        painter.setBrush(QColor(30, 30, 30, 128))
                    else:
                        painter.setBrush(C_VALUE_BG)

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(r_val, 4, 4)

                    painter.setPen(C_VALUE_TEXT)
                    painter.setFont(value_font)
                    painter.drawText(r_val, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
                
                current_y += (PIN_ROW_HEIGHT * 2)
            else:
                current_y += PIN_ROW_HEIGHT
            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(C_RESIZE_HANDLE)
        poly = QPolygonF()
        poly.append(QPointF(self.width, self.height))
        poly.append(QPointF(self.width - 12, self.height))
        poly.append(QPointF(self.width, self.height - 12))
        painter.drawPolygon(poly)

    def _draw_exec_pin(self, painter, x, y, pin_name, is_input):
        if is_input:
            is_connected = pin_name in self.node_data.connected_inputs
        else:
            is_connected = pin_name in self.node_data.connected_outputs

        poly = QPolygonF()
        size = 5
        poly.append(QPointF(x - size, y - size - 1)) 
        poly.append(QPointF(x - size, y + size + 1)) 
        poly.append(QPointF(x + size, y)) 
        
        if is_connected:
            painter.setBrush(Qt.GlobalColor.white)
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush) 
            painter.setPen(QPen(Qt.GlobalColor.white, 1.5))

        painter.drawPolygon(poly)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node_data.x = int(value.x())
            self.node_data.y = int(value.y())
            self.positionChanged.emit(self)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.AltModifier and event.button() == Qt.MouseButton.LeftButton:
            if self.is_reroute:
                self.app.delete_node(self.node_data)
                event.accept()
                return
        local_pos = event.pos()
        self.force_close_editor()

        hit_box = self.get_hit_value_box(local_pos)
        if hit_box:
            index, is_input, full_text, rect = hit_box
            self.start_editing_value(index, is_input, full_text, rect)
            event.accept()
            return
            
        # --- FIX: Block Resizing for Reroute Nodes ---
        if not self.is_reroute and (local_pos.x() > self.width - 15 and local_pos.y() > self.height - 15):
            self._resizing = True
            self._resize_start_pos = event.scenePos()
            self._resize_start_size = (self.width, self.height)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            diff = event.scenePos() - self._resize_start_pos
            new_w = max(self.min_width, self._resize_start_size[0] + diff.x())
            new_h = max(self.min_height, self._resize_start_size[1] + diff.y())
            self.prepareGeometryChange()
            self.width = new_w
            self.height = new_h
            self.update_editor_geometry()
            self.positionChanged.emit(self)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

# --------------------------------------------------------------------- #
# LINK ITEM
# --------------------------------------------------------------------- #
class UELinkItem(QGraphicsPathItem):
    def __init__(self, src_item, src_pin, dst_item, dst_pin, app):
        super().__init__()
        self.src_item = src_item
        self.src_pin = src_pin
        self.dst_item = dst_item
        self.dst_pin = dst_pin
        self.app = app 
        
        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.update_path()

    def update_path(self):
        start_pos = self.src_item.get_pin_geometry(self.src_pin, is_input=False)
        end_pos = self.dst_item.get_pin_geometry(self.dst_pin, is_input=True)
        path = QPainterPath()
        path.moveTo(start_pos)
        dx = end_pos.x() - start_pos.x()
        ctrl_dist = max(abs(dx) * 0.5, 50) 
        path.cubicTo(QPointF(start_pos.x() + ctrl_dist, start_pos.y()), QPointF(end_pos.x() - ctrl_dist, end_pos.y()), end_pos)
        self.setPath(path)
        
        # FIX: Use is_exec_name() for the fallback check
        is_exec_pin = (self.src_pin in self.src_item.node_data.exec_out_pins) or \
                      is_exec_name(self.src_pin)
                      
        pen_width = 3 if is_exec_pin else 1.5
        pen = QPen(C_LINK, pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)

    def shape(self):
        path = self.path()
        stroker = QPainterPathStroker()
        stroker.setWidth(15) 
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        return stroker.createStroke(path)
    
    def mousePressEvent(self, event):
        event.accept()
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.app.delete_link(self)
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = event.scenePos()
        self.app.create_knot_on_link(self, pos)
        event.accept()

# --------------------------------------------------------------------- #
# MAIN APP
# --------------------------------------------------------------------- #

class BlueprintView(QGraphicsView):
    def __init__(self, scene, app, parent=None):
        super().__init__(scene, parent)
        self.app = app
        self.setAcceptDrops(True) 
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(C_BACKGROUND))
        self._middle_pressed = False
        self._last_mouse_pos = None
        self._drag_wire = None
        self._drag_start_node = None
        self._drag_start_pin = None
        self._drag_start_is_input = False
        self._right_click_start_pos = None

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        grid_size = 50
        
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        
        right = int(rect.right()) + grid_size
        bottom = int(rect.bottom()) + grid_size

        for x in range(left, right, grid_size):
            painter.setPen(QPen(C_GRID_LIGHT if x % 150 == 0 else C_GRID_DARK, 1))
            painter.drawLine(x, top, x, bottom)

        for y in range(top, bottom, grid_size):
            painter.setPen(QPen(C_GRID_LIGHT if y % 150 == 0 else C_GRID_DARK, 1))
            painter.drawLine(left, y, right, y)

    # --- DRAG & DROP HANDLERS FOR THE STAGE ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
    def keyPressEvent(self, event):
        # [MODIFIED] Check if a text field (Proxy Widget) has focus
        # If yes, let the widget handle the key (e.g. deleting text), do not delete the node.
        focus_item = self.scene().focusItem()
        if isinstance(focus_item, QGraphicsProxyWidget):
            super().keyPressEvent(event)
            return
        # 1. DELETE / BACKSPACE
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            self.app.delete_selection()
            event.accept()
            return

        # 2. CTRL+C (Copy)
        if event.matches(QKeySequence.StandardKey.Copy) or (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_C):
            self.app.copy_selection()
            event.accept()
            return

        # 3. CTRL+V (Paste)
        if event.matches(QKeySequence.StandardKey.Paste) or (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V):
            # Paste at mouse cursor position
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            scene_pos = self.mapToScene(cursor_pos)
            self.app.paste_from_clipboard(scene_pos)
            event.accept()
            return

        super().keyPressEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        # Delegate the logic to the main app instance
        self.app.handle_dropped_files(files)

    def mousePressEvent(self, event):
        # 1. Handle Panning (Middle/Right Click)
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.RightButton): 
            self._middle_pressed = True
            self._last_mouse_pos = event.position().toPoint()
            if event.button() == Qt.MouseButton.RightButton:
                self._right_click_start_pos = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # 2. Handle Left Click
        if event.button() == Qt.MouseButton.LeftButton:

            if hasattr(self.app, 'node_items'):
                for item in self.app.node_items.values():
                    if hasattr(item, 'force_close_editor'):
                        item.force_close_editor()

            self.scene().setFocusItem(None)

            if event.modifiers() != Qt.KeyboardModifier.AltModifier:
                pos = self.mapToScene(event.position().toPoint())
                items = self.scene().items(pos)
                for item in items:
                    if isinstance(item, UENodeItem):
                        hit = item.hit_test_pin(pos)
                        if hit:
                            pin_name, is_input = hit
                            self.start_connection_drag(item, pin_name, is_input, pos)
                            return 
            # --- FIX END ---
        
        super().mousePressEvent(event)

    def start_connection_drag(self, node, pin, is_input, pos):
        self._drag_start_node = node
        self._drag_start_pin = pin
        self._drag_start_is_input = is_input
        self._drag_wire = QGraphicsPathItem()
        pen = QPen(Qt.GlobalColor.white, 2, Qt.PenStyle.DashLine)
        self._drag_wire.setPen(pen)
        self.scene().addItem(self._drag_wire)
        self.update_drag_wire(pos)

    def mouseMoveEvent(self, event):
        if self._middle_pressed:
            current_pos = event.position().toPoint()
            delta = current_pos - self._last_mouse_pos
            self._last_mouse_pos = current_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        elif self._drag_wire:
            pos = self.mapToScene(event.position().toPoint())
            self.update_drag_wire(pos)
        else:
            super().mouseMoveEvent(event)

    def update_drag_wire(self, mouse_pos):
        start_pos = self._drag_start_node.get_pin_geometry(self._drag_start_pin, self._drag_start_is_input)
        path = QPainterPath()
        path.moveTo(start_pos)
        dx = mouse_pos.x() - start_pos.x()
        ctrl_dist = max(abs(dx) * 0.5, 50)
        c1 = QPointF(start_pos.x() + ctrl_dist, start_pos.y())
        c2 = QPointF(mouse_pos.x() - ctrl_dist, mouse_pos.y())
        path.cubicTo(c1, c2, mouse_pos)
        self._drag_wire.setPath(path)

    def mouseReleaseEvent(self, event):
        if self._middle_pressed:
            self._middle_pressed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if event.button() == Qt.MouseButton.RightButton and self._right_click_start_pos:
                dist = (event.globalPosition().toPoint() - self._right_click_start_pos).manhattanLength()
                # If moved less than 5 pixels, treat as a Click, not a Drag
                if dist < 5:
                    cursor_pos = QCursor.pos()
                    # Open the palette
                    dlg = NodePaletteDialog(self.app, self.mapToScene(self.mapFromGlobal(cursor_pos)))
                    dlg.move(cursor_pos)
                    dlg.exec()
                self._right_click_start_pos = None
            event.accept()
        elif self._drag_wire:
            pos = self.mapToScene(event.position().toPoint())
            items = self.scene().items(pos)
            valid_drop = False
            for item in items:
                if isinstance(item, UENodeItem) and item != self._drag_start_node:
                    hit = item.hit_test_pin(pos)
                    if hit:
                        pin_name, is_input = hit
                        if is_input != self._drag_start_is_input:
                            if is_input:
                                self.app.create_link(self._drag_start_node, self._drag_start_pin, item, pin_name)
                            else:
                                self.app.create_link(item, pin_name, self._drag_start_node, self._drag_start_pin)
                            valid_drop = True
                            break
            self.scene().removeItem(self._drag_wire)
            self._drag_wire = None
            self._drag_start_node = None
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self.mapToScene(event.position().toPoint())
        items = self.scene().items(pos)
        
        # 1. Check if we hit a link (let the Link Item handle it)
        for item in items:
            if isinstance(item, UELinkItem):
                super().mouseDoubleClickEvent(event)
                return

        # 2. Check if we hit a Node (Edit Node)
        target_node = None
        for item in items:
            if isinstance(item, UENodeItem):
                target_node = item
                break
        
        if target_node:
            self.app.edit_node(target_node)
        else:
            # 3. Create New Node (only if empty space)
            self.app.create_node_at(pos)
        
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0
        factor = 1.1 if zoom_in else 0.9
        self.scale(factor, factor)

class ClickableLabel(QLabel):
    clicked = Signal() 
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class NodePaletteDialog(QDialog):
    def __init__(self, parent=None, pos=QPointF(0,0)):
        super().__init__(parent)
        self.app = parent
        self.spawn_pos = pos
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(250, 300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Search Bar
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("search_placeholder"))
        self.search.textChanged.connect(self.on_search)
        layout.addWidget(self.search)
        
        # List
        self.list = QListWidget()
        self.list.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list)
        
        # Populate
        self.keys = sorted(list(self.app.raw_node_templates.keys()), key=lambda x: x.lower())
        for k in self.keys:
            display = k.split("::")[0] if "::" in k else k
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, k)
            self.list.addItem(item)
            
        self.search.setFocus()

    def on_search(self, text):
        search_term = text.lower().replace(" ", "")
        for i in range(self.list.count()):
            item = self.list.item(i)
            raw_name = item.text()
            clean_name = raw_name.lower().replace(" ", "")
            item.setHidden(search_term not in clean_name)

    def on_item_clicked(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        self.app.spawn_template_node(key, self.spawn_pos)
        self.close()

# ==========================================
#          AI SYSTEM CLASSES
# ==========================================
class AIWorker(QThread):
    chunk_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    # Changed: receives 'messages_payload' (a list) instead of single user_msg
    def __init__(self, api_url, api_key, model, messages_payload):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.messages_payload = messages_payload # Store the full list

    def run(self):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": self.messages_payload,
            "stream": True
        }
        
        try:
            # 1. Prepare Data (Encode to bytes)
            json_data = json.dumps(data).encode('utf-8')
            
            # 2. Create Request Object
            req = urllib.request.Request(self.api_url, data=json_data, headers=headers, method="POST")
            
            # 3. Execute and Stream
            with urllib.request.urlopen(req) as response:
                # Iterate over lines directly from the response object
                for line in response:
                    if line:
                        # Decode bytes to string
                        decoded = line.decode('utf-8').strip()
                        
                        # Parse Server-Sent Events (SSE) format
                        if decoded.startswith("data: "):
                            content_str = decoded[6:] # Remove "data: " prefix
                            if content_str == "[DONE]": break
                            
                            try:
                                json_chunk = json.loads(content_str)
                                if 'choices' in json_chunk and len(json_chunk['choices']) > 0:
                                    delta = json_chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        self.chunk_received.emit(delta['content'])
                            except json.JSONDecodeError: 
                                pass
                                
            self.finished.emit()
            
        except urllib.error.HTTPError as e:
            self.error.emit(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            self.error.emit(f"Connection Error: {e.reason}")
        except Exception as e:
            self.error.emit(str(e))

class AISettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("lbl_ai_config_win"))
        self.resize(500, 200) 
        
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 1. API URL (Load from CONFIG)
        self.url_edit = QLineEdit(CONFIG.data.get("ai_url", ""))
        self.url_edit.setPlaceholderText("https://api.deepseek.com/chat/completions")
        form.addRow(T("lbl_api"), self.url_edit)

        # 2. API Key (Load from CONFIG)
        self.key_edit = QLineEdit(CONFIG.data.get("ai_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(T("lbl_api_key"), self.key_edit)

        # 3. Model Name (Dropdown + Custom Input)
        model_layout = QHBoxLayout()
        
        # --- FIX 1: Language Toggle for 'Custom' ---
        self.custom_label = "自定义" if CURRENT_LANG == "CN" else "Custom"
        
        # Define Presets
        self.presets = [
            "deepseek-chat", 
            "deepseek-reasoner", 
            "gpt-4o", 
            "gemini-3.0-pro",
            "gemini-2.5-flash",
            self.custom_label
        ]
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.presets)
        
        # --- FIX 2: Make Dropdown Wider ---
        self.model_combo.setMinimumWidth(200) 
        
        # Load current model from config
        current_model = CONFIG.data.get("ai_model", "")
        
        self.model_edit = QLineEdit(current_model)
        self.model_edit.setPlaceholderText(T("ph_enter"))
        
        # Initialize Logic: Check if current model is a preset or custom
        # We check if it is in presets AND it is not the "Custom" label itself
        if current_model in self.presets and current_model != self.custom_label:
            self.model_combo.setCurrentText(current_model)
            self.model_edit.setEnabled(False)
        else:
            # It's a custom value (or the word "Custom" from an old save)
            self.model_combo.setCurrentText(self.custom_label)
            self.model_edit.setEnabled(True)

        # Connect the signal
        self.model_combo.currentTextChanged.connect(self.on_model_change)

        # Add to layout with stretch factors (Combo gets more space now)
        model_layout.addWidget(self.model_combo, 1) 
        model_layout.addWidget(self.model_edit, 1)

        form.addRow(T("lbl_model"), model_layout)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # Manually set text using your translation function T()
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(T("btn_ok"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(T("btn_cancel"))

        btns.accepted.connect(self.save_settings)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def on_model_change(self, text):
        """Handles switching between Presets and Custom mode, and Auto-Fills URL"""
        
        # 1. Auto-Fill URL based on Model Selection
        if "gemini" in text.lower():
            self.url_edit.setText("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
        elif "deepseek" in text.lower():
            self.url_edit.setText("https://api.deepseek.com/chat/completions")
        elif "gpt" in text.lower():
            self.url_edit.setText("https://api.openai.com/v1/chat/completions")

        # 2. Handle Custom Input Logic
        if text == self.custom_label:
            self.model_edit.setEnabled(True)
            self.model_edit.setFocus()
            self.model_edit.selectAll()
        else:
            self.model_edit.setText(text)
            self.model_edit.setEnabled(False)

    def save_settings(self):
        # Save to global CONFIG
        CONFIG.data["ai_url"] = self.url_edit.text().strip()
        CONFIG.data["ai_key"] = self.key_edit.text().strip()
        # We always save the text from the Edit box
        CONFIG.data["ai_model"] = self.model_edit.text().strip()
        CONFIG.save()
        self.accept()

class AIChatWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        
        # --- 1. HISTORY STORAGE ---
        self.history = [] 
        self.current_ai_buffer = "" 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Output Area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        # Standardize Font and Background
        self.output.setStyleSheet("background-color: #252525; font-family: Microsoft YaHei UI; font-size: 10pt;")
        self.output.setPlaceholderText(T("ph_chat"))
        layout.addWidget(self.output)
        
        # Input Area
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(5, 5, 5, 5)
        
        # Input Section
        self.btn_clear = QPushButton("🗑️") 
        self.btn_clear.setFixedSize(40, 50)
        self.btn_clear.setToolTip(T("tlp_clear_history"))
        self.btn_clear.clicked.connect(self.clear_history)
        
        self.input = QTextEdit()
        self.input.setFixedHeight(50)
        self.input.setStyleSheet("color: #FFFFFF;") 
        
        self.btn_send = QPushButton(T("btn_send"))
        self.btn_send.setFixedSize(60, 50)
        self.btn_send.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input)
        input_layout.addWidget(self.btn_send)
        input_layout.addWidget(self.btn_clear)

        layout.addLayout(input_layout)
        
        # Status
        self.lbl_status = QLabel(T("lbl_ready"))
        self.lbl_status.setStyleSheet("color: #777; font-size: 8pt; padding-bottom: 8px;")
        layout.addWidget(self.lbl_status)

    def clear_history(self):
        """Resets the memory"""
        self.history = []
        self.output.clear()
        self.lbl_status.setText(T("lbl_ready"))

    def send_message(self):
        msg = self.input.toPlainText().strip()
        if not msg: return
        
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # 1. Insert Timestamp (CENTER ALIGNED)
        fmt_center = QTextBlockFormat()
        fmt_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fmt_center.setTopMargin(15) 
        fmt_center.setBottomMargin(5)
        cursor.insertBlock(fmt_center)
        
        now = datetime.datetime.now().strftime("%H:%M:%S")
        cursor.insertHtml(f"<span style='color: #666666; font-size: 9pt;'>{now}</span>")

        # 2. Insert User Message (LEFT ALIGNED)
        fmt_left = QTextBlockFormat()
        fmt_left.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cursor.insertBlock(fmt_left)
        
        formatted_msg = msg.replace('\n', '<br>')
        cursor.insertHtml(f"<span style='color: #FFFFFF; font-weight: bold;'>User: </span><span style='color: #DDDDDD;'>{formatted_msg}</span>")

        # 3. Insert AI Label (LEFT ALIGNED)
        cursor.insertBlock(fmt_left)
        cursor.insertHtml("<span style='color: #88C0D0;'>AI: </span>")
        
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

        # UI Cleanup
        self.input.clear()
        self.input.setDisabled(True)
        self.btn_send.setDisabled(True)
        self.lbl_status.setText(T("lbl_think"))
        
        # --- 3. BUILD CONTEXT & SEND ---
        
        # A. Add User Msg to History
        self.history.append({"role": "user", "content": msg})

        # B. Prepare Full Payload (System + History)
        sys_prompt = SPEC_CN if CURRENT_LANG == "CN" else SPEC_EN
        full_context = [{"role": "system", "content": sys_prompt}] + self.history

        # C. Reset Buffer
        self.current_ai_buffer = ""

        # Config
        url = CONFIG.data.get("ai_url", "https://api.deepseek.com/chat/completions")
        key = CONFIG.data.get("ai_key", "")
        model = CONFIG.data.get("ai_model", "deepseek-reasoner")

        if "openai.com" in url or "deepseek" in url:
            if not key:
                self.output.append("<span style='color:orange'>Warning: No API Key found.</span>")

        # NOTE: Make sure your AIWorker class is updated to accept 'full_context' (list) 
        # instead of 'sys_prompt, msg' (strings).
        self.worker = AIWorker(url, key, model, full_context)
        self.worker.chunk_received.connect(self.update_stream)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def update_stream(self, text):
        # Accumulate text for history
        self.current_ai_buffer += text
        
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        if cursor.blockFormat().alignment() != Qt.AlignmentFlag.AlignLeft:
             fmt = QTextBlockFormat()
             fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)
             cursor.setBlockFormat(fmt)

        cf = QTextCharFormat()
        cf.setForeground(QColor("#88C0D0"))
        cursor.insertText(text, cf)
        
        scrollbar = self.output.verticalScrollBar()
        was_at_bottom = (scrollbar.value() >= scrollbar.maximum() - 20)
        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def on_finished(self):
        # --- 4. SAVE AI RESPONSE ---
        if self.current_ai_buffer:
             self.history.append({"role": "assistant", "content": self.current_ai_buffer})

        self.input.setDisabled(False)
        self.btn_send.setDisabled(False)
        self.input.setFocus()
        self.lbl_status.setText(T("lbl_ready"))

    def on_error(self, err):
        self.output.append(f"<div style='color: #FF5555;'>Error: {err}</div>")
        self.on_finished()

class UEGraphApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UE5 Blueprint Viewer")
        self.resize(1200, 800)
        self.nodes = {} 
        self.links = [] 
        self.node_items = {} 
        self.link_items = [] 
        self.raw_node_templates = {}
        self.setAcceptDrops(True) 

        # Load Global Configs
        global CURRENT_LANG
        CURRENT_LANG = CONFIG.data["language"]
        self.raw_node_templates = {}
        
        self.init_ui()
        
        # Load Templates if enabled
        if CONFIG.data["enable_saving"]:
            self.check_legacy_templates()
            # Use QTimer to delay execution until the UI is fully drawn
            QTimer.singleShot(100, self.load_templates_from_disk)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        
        # --- Toolbar ---
        self.toolbar_layout = QHBoxLayout() 
        self.toolbar_layout.setContentsMargins(7,7,7,0) 

        self.btn_show = QPushButton()
        self.btn_show.clicked.connect(self.show_current_graph)
        self.toolbar_layout.addWidget(self.btn_show)

        self.btn_sort = QPushButton()
        self.btn_sort.clicked.connect(self.auto_sort_nodes)
        self.toolbar_layout.addWidget(self.btn_sort)

        self.toolbar_layout.addSpacing(10)
        
        self.chk_coords = QCheckBox()
        self.chk_coords.setToolTip("")
        self.chk_coords.setChecked(CONFIG.data["show_coords"]) 
        self.chk_coords.toggled.connect(self.on_coords_changed)
        self.toolbar_layout.addWidget(self.chk_coords)

        self.toolbar_layout.addSpacing(10)
        
        # Search Box
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(T("search_placeholder"))
        self.txt_search.setFixedWidth(150)
        self.txt_search.textChanged.connect(self.on_search_text_changed)
        self.toolbar_layout.addWidget(self.txt_search)
        
        self.toolbar_layout.addStretch()
        
        # AI Checkbox
        self.chk_ai = QCheckBox("AI")
        self.chk_ai.setChecked(False)
        self.chk_ai.toggled.connect(self.toggle_ai_dock)
        self.toolbar_layout.addWidget(self.chk_ai)
        # Hide by default unless unlocked in config
        self.chk_ai.setVisible(CONFIG.data.get("ai_unlocked", False))

        # Setting button
        self.btn_setting = QPushButton()
        self.btn_setting.clicked.connect(self.open_setting)
        self.toolbar_layout.addWidget(self.btn_setting)

        # Spec button
        self.btn_spec = QPushButton()
        self.btn_spec.clicked.connect(self.show_spec_dialog)
        self.toolbar_layout.addWidget(self.btn_spec)

        # Add Language Toggle directly to Toolbar
        self.lbl_lang = ClickableLabel("Eng/中", self)
        self.lbl_lang.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_lang.setStyleSheet("""
            QLabel {
                background-color: transparent;
                font-size: 11px;
                font-family: "Microsoft YaHei UI", sans-serif;
                padding-left: 10px; /* Add some spacing */
            }
        """)
        self.lbl_lang.clicked.connect(self.toggle_language)
        # Add to layout so it moves automatically with the window
        self.toolbar_layout.addWidget(self.lbl_lang)
        
        layout.addLayout(self.toolbar_layout)
        
        # --- Graph View ---
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(-50000, -50000, 100000, 100000)
        self.view = BlueprintView(self.scene, self)
        layout.addWidget(self.view)

        # AI Dock Widget
        self.dock_ai = QDockWidget("AI Assistant", self)
        self.dock_ai.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        
        # --- FIX 4 & 5: Padding and Removing Buttons ---
        # 1. Remove Close (X) and Float buttons, but keep it Movable (draggable)
        # Allow both moving (within dock areas) and floating (detaching as window)
        self.dock_ai.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                                 QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        
        # 2. Styling the Title Bar for Padding
        # Note: Styling QDockWidget title bars can vary by OS, but this is the standard QT stylesheet approach
        self.dock_ai.setStyleSheet("""
            QDockWidget::title {
                text-align: center;
                background: #333333;
                padding-top: 10px;    /* Add top padding */
                padding-bottom: 10px; /* Add bottom padding */
                spacing: 10px;
            }
        """)

        self.chat_widget = AIChatWidget(self)
        self.dock_ai.setWidget(self.chat_widget)
        self.dock_ai.hide() 
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_ai)

        self.update_ui_text()

    # Add this method to UEGraphApp class
    def toggle_ai_dock(self, checked):
        if checked:
            self.dock_ai.show()
            # Try to set width to 1/3 of the window
            width = self.width() // 3
            self.resizeDocks([self.dock_ai], [width], Qt.Orientation.Horizontal)
        else:
            self.dock_ai.hide()

    def check_legacy_templates(self):
        """Checks for old template format (keys without context) and removes file if found."""
        path = CONFIG.data["template_path"]
        if not os.path.exists(path): return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            has_legacy = False
            # These are common nodes that DEFINITELY need context now.
            # If we find the "naked" version, it's an old file.
            problematic_keys = ["Is Valid::FUNC", "Get::FUNC", "Set::FUNC"]
            
            for k in data.keys():
                if k in problematic_keys:
                    has_legacy = True
                    break
            
            if has_legacy:
                # Close file handle by exiting with-block before removal
                pass 
                
                # Delete the file
                os.remove(path)
                self.raw_node_templates = {}
                
                # Show the message
                msg_en = "Template format has updated, to avoid data conflicts, the old templates are removed"
                msg_cn = "模板格式已更新,为了避免数据冲突,旧模板已被移除"
                
                msg = msg_cn if CURRENT_LANG == "CN" else msg_en
                self.show_flash_message(msg)
                
        except Exception as e:
            print(f"Legacy check failed: {e}")

    def spawn_template_node(self, key, pos):
        if key not in self.raw_node_templates: return
        
        raw_text = self.raw_node_templates[key]
        
        # 1. Generate Unique Internal Name
        existing_internals = {n.internal_name for n in self.nodes.values()}
        
        # Extract Class for nice internal naming
        class_match = re.search(r'Class=[\w\./]+\.([^ "\']+)', raw_text)
        class_prefix = class_match.group(1) if class_match else "Node"
        
        int_cnt = 1
        new_internal = f"{class_prefix}_{int_cnt}"
        while new_internal in existing_internals:
            int_cnt += 1
            new_internal = f"{class_prefix}_{int_cnt}"
            
        # 2. Freshen GUIDs and Inject New Internal Name
        final_text = self.freshen_raw_template(raw_text, new_internal)
        
        # 3. Update Position (Inject Mouse X/Y)
        final_text = re.sub(r'NodePosX=(-?\d+)', f'NodePosX={int(pos.x())}', final_text)
        final_text = re.sub(r'NodePosY=(-?\d+)', f'NodePosY={int(pos.y())}', final_text)

        # 4. Create Node Data
        data = get_node_data(final_text)
        
        # 5. Visual Name Resolution
        base_visual = data['type']
        # Clean suffix from template name if present
        base_visual = re.sub(r'_\d+$', '', base_visual).strip()
        
        new_name = base_visual
        if new_name in self.nodes:
            cnt = 1
            while f"{base_visual}_{cnt}" in self.nodes:
                cnt += 1
            new_name = f"{base_visual}_{cnt}"

        # 6. Build Object
        new_node = NodeData(new_name)
        new_node.internal_name = new_internal # Use the one we generated
        new_node.raw_text = final_text
        new_node.x = int(pos.x())
        new_node.y = int(pos.y())
        
        # Parse Pins
        for p in data['pins']:
            pin_str = p['name']
            if p['dir'] == "IN" and p['value'] and not p['links']:
                    pin_str = f"{p['name']}\\({p['value']}\\)"

            if p.get('category') == 'exec':
                if p['dir'] == "IN": new_node.exec_in_pins.append(pin_str)
                else: new_node.exec_out_pins.append(pin_str)
            else:
                if p['dir'] == "IN": new_node.add_input(pin_str)
                else: new_node.add_output(pin_str)

        self.nodes[new_name] = new_node
        self.add_node_visual(new_node)
        
        if new_name in self.node_items:
            self.node_items[new_name].setSelected(True)

    def open_setting(self):
        dlg = SettingDialog(self)
        dlg.exec()

    def on_coords_changed(self, checked):
        CONFIG.data["show_coords"] = checked
        CONFIG.save()

    def load_templates_from_disk(self):
        path = CONFIG.data["template_path"]
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.raw_node_templates = json.load(f)
                count = len(self.raw_node_templates)
                
                self.show_flash_message(T("msg_tpl_loaded").format(count))
            except Exception as e:
                print(f"Load template failed: {e}")
        else:
            # Prompt requirement: Warning if missing
            self.show_flash_message(T("msg_tpl_missing").format(path))

    def save_templates_to_disk(self):
        if not CONFIG.data["enable_saving"]: return
        path = CONFIG.data["template_path"]
        
        # Ensure dir exists
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.raw_node_templates, f, indent=4)
        except Exception as e:
            print(f"Save template failed: {e}")

    def update_template_library(self, new_blocks):
        """Merges new blocks and saves."""
        new_count = 0
        dup_count = 0
        
        for block in new_blocks:
            data = get_node_data(block)
            base_visual = data['type']
            clean_visual_key = re.sub(r'_\d+$', '', base_visual).strip()
            
            # --- Key Generation Logic ---
            c_match = re.search(r'Class=[\w\./]+\.([^ "\']+)', block)
            c_name = c_match.group(1) if c_match else ""
            
            t_suffix = "FUNC" 
            if "K2Node_CustomEvent" in c_name or "K2Node_Event" in c_name:
                t_suffix = "EVT"
            
            context = get_context_suffix(block)
            
            final_display_name = clean_visual_key
            if context and (context.lower() not in clean_visual_key.lower()):
                final_display_name = f"{clean_visual_key} ({context})"
                
            key = f"{final_display_name}::{t_suffix}"
            # ---------------------------
            
            if key in self.raw_node_templates:
                dup_count += 1
                # [FIXED] Found existing template? Skip! 
                # This ensures the old (existing) template is KEPT and not overwritten.
                continue 
            else:
                new_count += 1
                self.raw_node_templates[key] = block
        
        total = len(self.raw_node_templates)
        detected = new_count + dup_count
        
        self.save_templates_to_disk()

        header = T("import_template")
        stats = T("msg_import_stat").format(detected, dup_count, new_count, total)
        full_msg = f"{header}\n{stats}"
        self.show_flash_message(full_msg)
    
    def on_search_text_changed(self, text):
        search_term = text.strip().lower()
        
        for name, item in self.node_items.items():
            if not search_term:
                item.is_highlighted = False
            else:
                # Search in Node Name (Visual Name)
                match_name = search_term in name.lower()
                
                # Optional: Search in Node Type/Class (Humanized)
                display_name = item.node_data.name.lower() # Or calculate display name logic
                match_display = search_term in display_name
                
                item.is_highlighted = (match_name or match_display)
            
            item.update() # Trigger repaint to show/hide green stroke

    def toggle_language(self):
        global CURRENT_LANG
        CURRENT_LANG = "CN" if CURRENT_LANG == "EN" else "EN"
        self.update_ui_text()
        CONFIG.data["language"] = CURRENT_LANG
        CONFIG.save()

    def update_ui_text(self):
        self.setWindowTitle(T("window_title"))
        self.btn_show.setText(T("btn_show"))
        self.btn_sort.setText(T("btn_sort"))
        self.btn_spec.setText(T("btn_spec"))
        self.chk_coords.setText(T("chk_coords"))
        self.chk_coords.setToolTip(T("tip_coords"))
        self.txt_search.setPlaceholderText(T("search_placeholder"))
        self.btn_setting.setText(T("btn_setting"))
        
        # 2. Update the Toggle Label with HTML
        
        if CURRENT_LANG == "EN":
            # Eng is active
            formatted_text = (
                "<span style='color:#FFFFFF; font-weight:bold;'>Eng</span>"
                "<span style='color:#777777;'> / </span>"
                "<span style='color:#777777;'>中</span>"
            )
        else:
            # CN is active
            formatted_text = (
                "<span style='color:#777777;'>Eng</span>"
                "<span style='color:#777777;'> / </span>"
                "<span style='color:#FFFFFF; font-weight:bold;'>中</span>"
            )

        self.lbl_lang.setText(formatted_text)
        self.lbl_lang.adjustSize()

    def _get_consumers(self, node):
        """Returns list of nodes that consume outputs from this node."""
        consumers = []
        for link in self.links:
            if link.src_node == node.name:
                if link.dst_node in self.nodes:
                    consumers.append(self.nodes[link.dst_node])
        return consumers

    def _get_connected_components(self):
        """Partitions all nodes into disjoint connected components (islands)."""
        visited = set()
        components = []
        
        # Sort keys to ensure deterministic processing order
        all_names = sorted(self.nodes.keys())
        
        for name in all_names:
            if name in visited: continue
            
            # BFS to find all connected nodes (Exec and Data links)
            group = []
            queue = [name]
            visited.add(name)
            
            while queue:
                curr = queue.pop(0)
                group.append(self.nodes[curr])
                
                # Find neighbors
                neighbors = []
                for link in self.links:
                    if link.src_node == curr and link.dst_node in self.nodes:
                        neighbors.append(link.dst_node)
                    if link.dst_node == curr and link.src_node in self.nodes:
                        neighbors.append(link.src_node)
                
                for n in neighbors:
                    if n not in visited:
                        visited.add(n)
                        queue.append(n)
            
            components.append(group)
        
        return components

    def _calculate_hybrid_ranks(self, nodes_subset):
        """
        Calculates ranks for a specific subset of nodes.
        """
        node_map = {n.name: n for n in nodes_subset}
        subset_names = set(node_map.keys())

        # 1. Initialize In-Degree (Only considering links within this subset)
        in_degree = {n: 0 for n in subset_names}
        adj = {n: [] for n in subset_names}
        
        for link in self.links:
            if link.src_node in subset_names and link.dst_node in subset_names:
                adj[link.src_node].append(link.dst_node)
                in_degree[link.dst_node] += 1

        # 2. Topological Sort (ASAP)
        ranks = {n: 0 for n in subset_names}
        queue = [n for n, d in in_degree.items() if d == 0]
        sorted_order = []

        while queue:
            u = queue.pop(0)
            sorted_order.append(u)
            
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
                ranks[v] = max(ranks[v], ranks[u] + 1)
        
        # 3. Backward Pass (ALAP) for Data Nodes
        for u_name in reversed(sorted_order):
            node = node_map[u_name]
            if not node.is_exec_node():
                consumers = []
                for link in self.links:
                    if link.src_node == u_name and link.dst_node in subset_names:
                        consumers.append(self.nodes[link.dst_node])
                
                if consumers:
                    min_consumer_rank = min([ranks[c.name] for c in consumers])
                    target_rank = min_consumer_rank - 1
                    ranks[u_name] = max(ranks[u_name], target_rank)

        return ranks

    def _is_node_overlapping(self, node_a, node_b, padding=20):
        """Checks if two nodes overlap with padding."""
        # Estimate dimensions if items exist, else default
        item_a = self.node_items.get(node_a.name)
        item_b = self.node_items.get(node_b.name)
        
        w_a = item_a.width if item_a else 200
        h_a = item_a.height if item_a else 100
        w_b = item_b.width if item_b else 200
        h_b = item_b.height if item_b else 100
        
        rect_a = QRectF(node_a.x - padding, node_a.y - padding, w_a + padding*2, h_a + padding*2)
        rect_b = QRectF(node_b.x, node_b.y, w_b, h_b)
        
        return rect_a.intersects(rect_b)

    def _resolve_overlaps(self, nodes_subset):
        """Pushes nodes in the subset apart to resolve collisions."""
        sorted_nodes = sorted(nodes_subset, key=lambda n: n.x)
        moved = True
        iter_count = 0
        
        while moved and iter_count < 5:
            moved = False
            iter_count += 1
            # Re-sort by Y primarily for vertical collision logic
            sorted_nodes.sort(key=lambda n: (n.x, n.y))
            
            for i in range(len(sorted_nodes)):
                for j in range(i + 1, len(sorted_nodes)):
                    n1 = sorted_nodes[i]
                    n2 = sorted_nodes[j]
                    
                    if n2.x > n1.x + 250: break 
                    
                    if self._is_node_overlapping(n1, n2):
                        item_n1 = self.node_items.get(n1.name)
                        h1 = item_n1.height if item_n1 else 100
                        
                        # Push n2 below n1
                        new_y = n1.y + h1 + 30
                        if n2.y < new_y:
                            n2.y = new_y
                            moved = True

    def center_viewport_on_nodes(self):
        """Calculates the center of all items and moves the viewport there."""
        rect = self.scene.itemsBoundingRect()
        if not rect.isNull():
            self.view.centerOn(rect.center())

    def show_flash_message(self, message):
        """Displays a temporary floating message in the center of the view."""
        # Create label parented to the view so it stays centered relative to the window
        lbl = QLabel(message, self.view)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("""
            background-color: rgba(0, 0, 0, 70);
            color: #FFFFFF;
            font-size: 16pt;
            font-weight: bold;
            padding: 15px 30px;
            border-radius: 10px;
            border: 1px solid #FFFFFF;
        """)
        lbl.adjustSize()
        
        # Center it
        view_rect = self.view.rect()
        lbl.move(view_rect.center() - lbl.rect().center())
        lbl.show()
        
        # Fade out/Destroy after 2 seconds
        QTimer.singleShot(2000, lbl.deleteLater)

    # ------------------- MAIN WINDOW DRAG HANDLERS ------------------- #
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.handle_dropped_files(files)

    def show_current_graph(self):
        simplified_content = self.get_graph_string(include_coords=self.chk_coords.isChecked())
        # Pass the simplified text AND the function reference to generate raw text
        dlg = ShowGraphDialog(simplified_content, self.generate_raw_t3d, self)
        dlg.exec()
    
    def get_blueprints_dir(self):
        """Returns the directory where blueprints are saved (same folder as template)."""
        template_path = CONFIG.data["template_path"]
        return os.path.dirname(template_path)

    def save_current_blueprint(self):
        # Setup Dialog
        dlg = QInputDialog(self)
        dlg.setWindowTitle(T("dlg_save_bp_title"))
        dlg.setLabelText(T("lbl_save_bp"))
        dlg.setOkButtonText(T("btn_ok"))
        dlg.setCancelButtonText(T("btn_cancel"))
        dlg.setTextValue("")
        
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        name = dlg.textValue()

        # 1. Check if Cancelled
        if not ok or not name.strip():
            return False

        name = re.sub(r'[\\/*?:"<>|]', "", name.strip()) # Sanitize
        root_dir = self.get_blueprints_dir()
        save_folder = os.path.join(root_dir, name)
        save_file = os.path.join(save_folder, f"{name}.json")

        # 2. Check overlap
        if os.path.exists(save_folder):
            # Using custom confirmation
            if not ask_confirmation(self, T("msg_err_title"), T("msg_bp_exists").format(name)):
                return False
        
        # 3. Serialize Data
        bp_data = {
            "nodes": [],
            "links": []
        }
        
        for n in self.nodes.values():
            node_dict = {
                "name": n.name,
                "internal_name": n.internal_name,
                "raw_text": n.raw_text,
                "x": n.x,
                "y": n.y,
                "exec_in": n.exec_in_pins,
                "exec_out": n.exec_out_pins,
                "data_in": n.data_inputs,
                "data_out": n.data_outputs
            }
            bp_data["nodes"].append(node_dict)
            
        for l in self.links:
            bp_data["links"].append({
                "src": l.src_node, "src_pin": l.src_pin,
                "dst": l.dst_node, "dst_pin": l.dst_pin
            })

        # 4. Write to file
        try:
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)
            
            with open(save_file, 'w', encoding='utf-8') as f:
                json.dump(bp_data, f, indent=4)
                
            self.show_flash_message(T("msg_bp_saved"))
            return True
        
        except Exception as e:
            QMessageBox.critical(self, T("msg_err_title"), T("msg_bp_err").format(e))
            return False

    def open_saved_blueprint(self):
        root_dir = self.get_blueprints_dir()
        if not os.path.exists(root_dir):
            self.show_flash_message(T("msg_no_bp"))
            return

        # Scan for folders containing json
        candidates = []
        for entry in os.scandir(root_dir):
            if entry.is_dir():
                json_path = os.path.join(entry.path, f"{entry.name}.json")
                if os.path.exists(json_path):
                    candidates.append(entry.name)
        
        if not candidates:
            self.show_flash_message(T("msg_no_bp"))
            return

        dlg = OpenBlueprintDialog(self, sorted(candidates))
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_blueprint:
            self.load_blueprint_json(root_dir, dlg.selected_blueprint)

    def load_blueprint_json(self, root_dir, name):
        file_path = os.path.join(root_dir, name, f"{name}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.merge_blueprint_data(data)
        except Exception as e:
            QMessageBox.critical(self, T("msg_err_title"), T("msg_bp_err").format(e))

    def merge_blueprint_data(self, bp_data):
        json_nodes = bp_data.get("nodes", [])
        json_links = bp_data.get("links", [])
        collected_raw_blocks = []
        # --- Avoid Overlap ---
        if self.nodes and json_nodes:
            # 1. Calculate Bounds of Existing Nodes
            ex_max_x = -float('inf')
            ex_min_y = float('inf')
            
            for n in self.nodes.values():
                item = self.node_items.get(n.name)
                # Estimate width if item not ready (fallback 250)
                w = item.width if item else 250 
                
                right = n.x + w
                if right > ex_max_x: ex_max_x = right
                if n.y < ex_min_y: ex_min_y = n.y
            
            # Handle case where ex_max_x is still -inf (e.g. empty nodes dict but not None)
            if ex_max_x == -float('inf'): ex_max_x = 0
            if ex_min_y == float('inf'): ex_min_y = 0

            # 2. Calculate Bounds of New Block
            new_min_x = min(node['x'] for node in json_nodes)
            new_min_y = min(node['y'] for node in json_nodes)
            
            # 3. Calculate Offsets
            # Target X: 100px padding to the right of the furthest existing node
            target_x = ex_max_x + 150
            offset_x = target_x - new_min_x
            
            # Target Y: Align the top of the new block with the top of existing nodes
            offset_y = ex_min_y - new_min_y
            
            # 4. Apply Offsets to the loaded data before processing
            for node in json_nodes:
                node['x'] += int(offset_x)
                node['y'] += int(offset_y)
        
        rename_map = {}
        existing_names = set(self.nodes.keys())
        existing_internals = {n.internal_name for n in self.nodes.values()}
        
        self.scene.clearSelection()

        # 1. Process Nodes (Collision Handling)
        for nd in json_nodes:
            old_name = nd["name"]
            new_name = old_name
            
            # Resolve Visual Name Collision
            if new_name in existing_names:
                # Find suffix
                base_name = re.sub(r'_\d+$', '', old_name)
                prefix = base_name + "_"
                max_suffix = 0
                for en in existing_names:
                    if en.startswith(prefix):
                        suffix = en[len(prefix):]
                        if suffix.isdigit():
                            max_suffix = max(max_suffix, int(suffix))
                new_name = f"{prefix}{max_suffix + 1}"
            
            rename_map[old_name] = new_name
            existing_names.add(new_name)
            
            # Create Node Data
            new_node = NodeData(new_name)
            new_node.x = nd["x"]
            new_node.y = nd["y"]
            new_node.exec_in_pins = nd.get("exec_in", [])
            new_node.exec_out_pins = nd.get("exec_out", [])
            new_node.data_inputs = nd.get("data_in", [])
            new_node.data_outputs = nd.get("data_out", [])
            
            # Handle Raw Text (Freshen GUIDs)
            raw = nd.get("raw_text", "")
            if raw:
                collected_raw_blocks.append(raw)
                # Resolve Internal Name Collision
                old_internal = nd.get("internal_name", "Unknown")
                new_internal = old_internal
                
                # Always freshen GUIDs, but check name
                # If we renamed the visual node, or if internal name collides
                if new_name != old_name or new_internal in existing_internals:
                    # Generate new internal name
                    cls_match = re.search(r'Class=[\w\./]+\.([^ "\']+)', raw)
                    cls = cls_match.group(1) if cls_match else "Node"
                    cnt = 1
                    test_internal = f"{cls}_{cnt}"
                    while test_internal in existing_internals:
                        cnt += 1
                        test_internal = f"{cls}_{cnt}"
                    new_internal = test_internal
                
                existing_internals.add(new_internal)
                new_node.internal_name = new_internal
                new_node.raw_text = self.freshen_raw_template(raw, new_internal)
            
            self.nodes[new_name] = new_node
            self.add_node_visual(new_node)
            if new_name in self.node_items:
                self.node_items[new_name].setSelected(True)

        # 2. Process Links
        for l in json_links:
            src = rename_map.get(l["src"], l["src"])
            dst = rename_map.get(l["dst"], l["dst"])
            
            if src in self.nodes and dst in self.nodes:
                 if src in self.node_items and dst in self.node_items:
                    self.create_link(
                        self.node_items[src], l["src_pin"],
                        self.node_items[dst], l["dst_pin"]
                    )
        
        self.recalc_connections()
        self.show_flash_message(T("msg_pasted").format(len(json_nodes)))

        if collected_raw_blocks:
            # This will check for duplicates, add new ones, and save to Templates.json
            self.update_template_library(collected_raw_blocks)

    def get_graph_string(self, include_coords=True):
        """Helper to generate the text representation of the graph."""
        lines = []
        lines.append("# --- Node Definitions ---")
        for name in sorted(self.nodes.keys()):
            node = self.nodes[name]
            ins = node.exec_in_pins + node.data_inputs
            outs = node.exec_out_pins + node.data_outputs
            
            base_name = re.sub(r'\s*\(.*?\)', '', name) # Strip context
            clean_name = base_name.replace(" ", "").strip() # Strip spaces
            
            in_str = "".join([f"{p};" for p in ins])
            out_str = "".join([f"{p};" for p in outs])
            
            lines.append(f"{clean_name} ({in_str}) : ({out_str})")
            
        lines.append("\n# --- Links ---")
        for link in self.links:
            # [MODIFIED] Apply same cleaning to Link names
            src = re.sub(r'\s*\(.*?\)', '', link.src_node).replace(" ", "").strip()
            dst = re.sub(r'\s*\(.*?\)', '', link.dst_node).replace(" ", "").strip()
            lines.append(f"{src} ({link.src_pin}) -> {dst} ({link.dst_pin})")
            
        if include_coords:
            lines.append("\n# --- Coordinates ---")
            for name in sorted(self.nodes.keys()):
                node = self.nodes[name]
                # [MODIFIED] Clean name
                base_name = re.sub(r'\s*\(.*?\)', '', name)
                clean_name = base_name.replace(" ", "").strip()
                lines.append(f"{clean_name} ({int(node.x)}; {int(node.y)})")
            
        return "\n".join(lines)

    def open_paste_dialog(self):
        dlg = DirectPasteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            text = dlg.get_text()
            if not text.strip(): return
            
            snapshot_positions = {}
            for name, node in self.nodes.items():
                snapshot_positions[name] = (node.x, node.y)

            t3d_positions = {}
            t3d_raw_map = {}
            t3d_internal_map = {}
            use_t3d = False

            if "Begin Object" in text and "End Object" in text:
                try:
                    text, t3d_positions, t3d_raw_map, t3d_internal_map = generate_spec_file(text)
                    use_t3d = True
                except Exception as e:
                    QMessageBox.critical(self, "Conversion Error", f"Failed to convert raw UE data: {e}")
                    return

            self.nodes.clear()
            self.links.clear()
            self.scene.clear()
            self.node_items.clear()
            self.link_items.clear()
            
            try:
                lines = text.split('\n')
                self.parse_lines(lines) 

                if use_t3d:
                    for name, (x, y) in t3d_positions.items():
                        if name in self.nodes:
                            self.nodes[name].x = x
                            self.nodes[name].y = y
                    for name, raw_txt in t3d_raw_map.items():
                        if name in self.nodes:
                            self.nodes[name].raw_text = raw_txt
                    for name, internal in t3d_internal_map.items():
                        if name in self.nodes:
                            self.nodes[name].internal_name = internal
                
                else:
                    for name, node in self.nodes.items():

                        if node.x == 0 and node.y == 0:
                            if name in snapshot_positions:
                                old_x, old_y = snapshot_positions[name]
                                node.x = old_x
                                node.y = old_y

                self.build_scene()
                self.recalc_connections()
                should_auto_sort = False
                
                if not use_t3d and not snapshot_positions:
                    all_zero = all(n.x == 0 and n.y == 0 for n in self.nodes.values())
                    if all_zero: should_auto_sort = True

                if should_auto_sort:
                    self.auto_sort_nodes()
            
                self.center_viewport_on_nodes()
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to parse pasted text: {e}")


    def generate_raw_t3d(self):
        output = []
        
        for name, node in self.nodes.items():
            if not node.raw_text:
                output.append(f"// Node {name} created manually (No Raw Text Available)")
                continue

            lines = node.raw_text.split('\n')
            new_lines = []
            
            for line in lines:
                # 1. Update Position
                if "NodePosX=" in line:
                    line = re.sub(r'NodePosX=(-?\d+)', f'NodePosX={int(node.x)}', line)
                if "NodePosY=" in line:
                    line = re.sub(r'NodePosY=(-?\d+)', f'NodePosY={int(node.y)}', line)
                    
                # 2. Update Values (DefaultValue)
                if "CustomProperties Pin" in line:
                    name_match = re.search(r'PinName="([^"]+)"', line)
                    if name_match:
                        raw_pin_name = name_match.group(1)
                        ui_pin_name = get_pin_ui_name(raw_pin_name, line)
                        
                        current_val = None
                        
                        # Search inputs
                        for p_str in node.data_inputs:
                            label = p_str
                            val = ""
                            has_val = False
                            val_match = re.match(r"^(.*?)\\\((.*)\\\)$", p_str)
                            if val_match:
                                label = val_match.group(1).strip()
                                val = val_match.group(2).strip()
                                has_val = True
                            label = re.sub(r'<.*?>', '', label)

                            if label == ui_pin_name and has_val:
                                current_val = val
                                break
                        
                        # Search outputs
                        if current_val is None:
                            for p_str in node.data_outputs:
                                label = p_str
                                val = ""
                                has_val = False
                                val_match = re.match(r"^(.*?)\\\((.*)\\\)$", p_str)
                                if val_match:
                                    label = val_match.group(1).strip()
                                    val = val_match.group(2).strip()
                                    has_val = True
                                label = re.sub(r'<.*?>', '', label)

                                if label == ui_pin_name and has_val:
                                    current_val = val
                                    break
                        
                        if current_val is not None:
                            safe_val = current_val.replace('"', '\\"') 
                            
                            # [FIX] Use regex search with \b to avoid detecting "AutogeneratedDefaultValue"
                            if re.search(r'\bDefaultValue="', line):
                                # [FIX] Robust regex to replace entire existing value including escaped quotes
                                line = re.sub(r'\bDefaultValue="((?:[^"\\]|\\.)*)"', f'DefaultValue="{safe_val}"', line)
                            else:
                                # (Rest of the append logic remains the same)
                                stripped = line.rstrip()
                                tail = line[len(stripped):]
                                if stripped.endswith(",)"):
                                    line = stripped[:-2] + f',DefaultValue="{safe_val}",)' + tail
                                elif stripped.endswith(")"):
                                    line = stripped[:-1] + f',DefaultValue="{safe_val}")' + tail
                                else:
                                    line = stripped + f',DefaultValue="{safe_val}"' + tail

                # 3. Rebuild Links (THE FIX)
                if "CustomProperties Pin" in line:
                    # A. Determine Direction of CURRENT Pin
                    is_output_pin = "Direction=\"EGPD_Output\"" in line
                    
                    # B. Clean Old Links
                    # This removes any existing "LinkedTo=(...)"
                    line = re.sub(r',?\s*LinkedTo=\([^\)]+\)', '', line)
                    
                    # C. CLEANUP SYNTAX BEFORE INJECTION
                    # We must strip the closing characters so we can append cleanly.
                    # This prevents the ",," and "))" bug.
                    line = line.rstrip()
                    has_trailing_comma = False
                    
                    if line.endswith(",)"):
                        line = line[:-2] # Remove ",)"
                    elif line.endswith(")"):
                        line = line[:-1] # Remove ")"
                    
                    # D. Identify Pin and Find Connections
                    guid_match = re.search(r'PinId=([A-F0-9]+)', line, re.IGNORECASE)
                    name_match = re.search(r'PinName="([^"]+)"', line)
                    
                    connected_targets = []
                    
                    if guid_match and name_match:
                        raw_pin_name = name_match.group(1)
                        ui_pin_name = get_pin_ui_name(raw_pin_name, line)

                        for l in self.links:
                            target_node_name = None
                            target_pin_ui_name = None

                            if is_output_pin:
                                if l.src_node == name and l.src_pin == ui_pin_name:
                                    target_node_name = l.dst_node
                                    target_pin_ui_name = l.dst_pin
                            else:
                                if l.dst_node == name and l.dst_pin == ui_pin_name:
                                    target_node_name = l.src_node
                                    target_pin_ui_name = l.src_pin
                            
                            if target_node_name:
                                target_node = self.nodes.get(target_node_name)
                                if target_node and target_node.raw_text:
                                    tgt_lines = target_node.raw_text.split('\n')
                                    for tl in tgt_lines:
                                        if "CustomProperties Pin" in tl:
                                            # Check Target Pin Direction
                                            t_is_output = "Direction=\"EGPD_Output\"" in tl

                                            if is_output_pin and t_is_output: continue
                                            if not is_output_pin and not t_is_output: continue

                                            t_name_m = re.search(r'PinName="([^"]+)"', tl)
                                            if t_name_m:
                                                t_raw_name = t_name_m.group(1)
                                                t_ui_res = get_pin_ui_name(t_raw_name, tl)
                                                
                                                if t_ui_res == target_pin_ui_name:
                                                    t_guid_m = re.search(r'PinId=([A-F0-9]+)', tl, re.IGNORECASE)
                                                    if t_guid_m:
                                                        connected_targets.append(f"{target_node.internal_name} {t_guid_m.group(1)}")
                                                    break

                    # E. Inject New Links
                    if connected_targets:
                        joined_links = ",".join(connected_targets)
                        # We append the LinkedTo block. We ensure a leading comma exists.
                        line += f",LinkedTo=({joined_links})"

                    # F. Close the line correctly
                    # UE5 properties generally end with ",)"
                    line += ",)"

                new_lines.append(line)
            
            output.append("\n".join(new_lines))
        
        return "\n".join(output)
    
    # ------------------- INTERACTIVE LOGIC ------------------- #
    def create_knot_on_link(self, link_item, pos):
        """Creates a Reroute Node (Knot) with correct Pin Types."""

        # 1. Gather Link Info
        src_node_name = link_item.src_item.node_data.name
        dst_node_name = link_item.dst_item.node_data.name
        src_pin = link_item.src_pin
        dst_pin = link_item.dst_pin
        
        # 2. Determine Pin Category
        # Check if source pin is Exec OR if it is in the source node's exec list (for chained knots)
        is_exec = is_exec_name(src_pin) or \
                  (src_pin in link_item.src_item.node_data.exec_out_pins) or \
                  is_exec_name(dst_pin)
                  
        pin_cat = "exec" if is_exec else "bool"

        # 3. Generate IDs
        internal_base = "K2Node_Knot"
        existing_internals = {n.internal_name for n in self.nodes.values()}
        cnt = 1
        internal_name = f"{internal_base}_{cnt}"
        while internal_name in existing_internals:
            cnt += 1
            internal_name = f"{internal_base}_{cnt}"

        visual_base = "RerouteNode"
        cnt = 1
        visual_name = f"{visual_base}_{cnt}"
        while visual_name in self.nodes:
            cnt += 1
            visual_name = f"{visual_base}_{cnt}"

        # 4. Generate UUIDs
        node_guid = uuid.uuid4().hex.upper()
        pin_in_id = uuid.uuid4().hex.upper()
        pin_out_id = uuid.uuid4().hex.upper()
        
        # 5. Construct Raw T3D Text
        raw_text = f"""Begin Object Class=/Script/BlueprintGraph.K2Node_Knot Name="{internal_name}" ExportPath="/Script/BlueprintGraph.K2Node_Knot'/Game/Blueprint/Core/GameMode/BP_GM.BP_GM:EventGraph.{internal_name}'"
   NodePosX={int(pos.x())}
   NodePosY={int(pos.y())}
   NodeGuid={node_guid}
   CustomProperties Pin (PinId={pin_in_id},PinName="InputPin",PinType.PinCategory="{pin_cat}",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,PinType.bSerializeAsSinglePrecisionFloat=False,PersistentGuid=00000000000000000000000000000000,bHidden=False,bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=True,bAdvancedView=False,bOrphanedPin=False,)
   CustomProperties Pin (PinId={pin_out_id},PinName="OutputPin",Direction="EGPD_Output",PinType.PinCategory="{pin_cat}",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,PinType.PinSubCategoryMemberReference=(),PinType.PinValueType=(),PinType.ContainerType=None,PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,PinType.bSerializeAsSinglePrecisionFloat=False,PersistentGuid=00000000000000000000000000000000,bHidden=False,bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,bAdvancedView=False,bOrphanedPin=False,)
End Object"""

        # 6. Create Node Data
        new_node = NodeData(visual_name) 
        new_node.internal_name = internal_name
        new_node.raw_text = raw_text
        new_node.x = int(pos.x())
        new_node.y = int(pos.y())
        
        # --- FIX: Manually categorize the pins based on is_exec ---
        # We use "Input Pin" / "Output Pin" (with space) to match T3D parser expectations
        if is_exec:
            new_node.exec_in_pins.append("Input Pin")
            new_node.exec_out_pins.append("Output Pin")
        else:
            new_node.data_inputs.append("Input Pin")
            new_node.data_outputs.append("Output Pin")
        # ---------------------------------------------------------
            
        self.nodes[visual_name] = new_node
        self.add_node_visual(new_node)
        
        # 7. Update Links
        self.delete_link(link_item)
        
        src_item = self.node_items[src_node_name]
        knot_item = self.node_items[visual_name]
        dst_item = self.node_items[dst_node_name]

        self.create_link(src_item, src_pin, knot_item, "Input Pin")
        self.create_link(knot_item, "Output Pin", dst_item, dst_pin)
        
        self.scene.clearSelection()
        knot_item.setSelected(True)

    def create_node_at(self, pos):
        dlg = NodeEditorDialog(self, "NewNode", ["Exec"], ["Exec"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.delete_requested: return 
            name, ins, outs = dlg.get_data()
            if not name: return
            base_name = name
            cnt = 1
            while name in self.nodes:
                name = f"{base_name}_{cnt}"
                cnt += 1
            node = NodeData(name)
            for i in ins: node.add_input(i)
            for o in outs: node.add_output(o)
            node.x = pos.x()
            node.y = pos.y()
            self.nodes[name] = node
            self.add_node_visual(node)

    def edit_node(self, item):
        node = item.node_data
        old_name = node.name 
        
        # 1. Clean display name for dialog
        display_name_for_edit = re.sub(r'\s*\(.*?\)', '', node.name).strip()

        # 2. Prepare pins for dialog (Use current state)
        # We strip spaces to be consistent with your PascalCase rules
        cur_ins = [p for p in (node.exec_in_pins + node.data_inputs)]
        cur_outs = [p for p in (node.exec_out_pins + node.data_outputs)]
        
        dlg = NodeEditorDialog(self, display_name_for_edit, cur_ins, cur_outs)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if dlg.delete_requested:
                self.delete_node(node)
                return
            
            new_name_raw, raw_new_ins, raw_new_outs = dlg.get_data()
            new_name = new_name_raw.strip()

            # --- HELPER: Fix Color Tags in Pin Strings ---
            def fix_pin_colors(pin_list):
                fixed_list = []
                for p_str in pin_list:
                    # Parse using global helper
                    label, val, has_val, _ = parse_pin_text(p_str)
                    
                    if has_val:
                        # 1. Remove old color tag from label if present
                        clean_label = re.sub(r'<.*?>', '', label)
                        
                        # 2. Check if value is a color and generate new tag
                        rgb_str = parse_ue_color(val)
                        if rgb_str:
                            clean_label = f"{clean_label}<{rgb_str}>"
                        
                        # 3. Reconstruct
                        fixed_list.append(f"{clean_label}\\({val}\\)")
                    else:
                        fixed_list.append(p_str)
                return fixed_list

            # Apply color fix to the new pins from dialog
            new_ins = fix_pin_colors(raw_new_ins)
            new_outs = fix_pin_colors(raw_new_outs)
            
            # Check if pins changed
            pins_changed = (cur_ins != new_ins) or (cur_outs != new_outs)

            # --- SMART RAW TEXT UPDATE ---
            # Default to clearing raw text if structure changes
            new_raw_text = ""
            
            # Only attempt to preserve Raw Text if we have it AND pin counts match
            # (If counts differ, user likely added/removed a pin, which breaks the T3D structure)
            if node.raw_text and len(new_ins) == len(node.exec_in_pins + node.data_inputs) and \
               len(new_outs) == len(node.exec_out_pins + node.data_outputs):
                
                temp_raw = node.raw_text
                update_success = True
                
                # Try update Inputs
                for p_str in new_ins:
                    label, val, has_val, _ = parse_pin_text(p_str)
                    if has_val:
                        # Use clean label to match PinName in raw text
                        ui_name = re.sub(r'<.*?>', '', label)
                        updated = update_raw_block_value(temp_raw, ui_name, val, is_input=True)
                        if updated:
                            temp_raw = updated
                        else:
                            # Failed to find pin in raw text? Abort smart update.
                            update_success = False
                            break
                
                # Try update Outputs
                if update_success:
                    for p_str in new_outs:
                        label, val, has_val, _ = parse_pin_text(p_str)
                        if has_val:
                            ui_name = re.sub(r'<.*?>', '', label)
                            updated = update_raw_block_value(temp_raw, ui_name, val, is_input=False)
                            if updated:
                                temp_raw = updated
                            else:
                                update_success = False
                                break
                
                if update_success:
                    new_raw_text = temp_raw

            # --- Rename Logic ---
            if new_name != old_name:
                if new_name in self.nodes:
                    if ask_confirmation(self, T("msg_name_taken_title"), T("msg_name_taken_text").format(new_name)):
                        base_name = new_name
                        cnt = 1
                        while new_name in self.nodes:
                            new_name = f"{base_name}_{cnt}"
                            cnt += 1
                    else:
                        new_name = old_name

                # Swap Dictionary Keys
                node.name = new_name
                del self.nodes[old_name]
                self.nodes[new_name] = node
                
                if old_name in self.node_items:
                    item_ref = self.node_items.pop(old_name)
                    self.node_items[new_name] = item_ref
                
                for link in self.links:
                    if link.src_node == old_name: link.src_node = new_name
                    if link.dst_node == old_name: link.dst_node = new_name
                
                # If we have valid raw text, update the name inside it too
                if new_raw_text:
                    # Simple replace for Name="Old" -> Name="New"
                    # We rely on the internal logic that the internal name usually matches the visual name suffix
                    # But if not, we invalidate. 
                    # For simplicity: Renaming usually invalidates Raw Text unless we parse deeper. 
                    # Let's keep it strict: Rename = Invalid Raw, UNLESS you want to implement 'Name=' regex replacement here.
                    # Given the request was about TextColor, we'll allow Rename to invalidate for safety, 
                    # OR try a simple replace if you prefer:
                    pass 

            # --- Update Pins ---
            if pins_changed:
                node.clear_pins()
                for i in new_ins: node.add_input(i)
                for o in new_outs: node.add_output(o)

            # --- Finalize Raw Text ---
            # If we successfully updated values (and didn't rename), use the new raw text.
            # Otherwise, if anything structural changed, it becomes empty.
            if new_name == old_name and new_raw_text:
                node.raw_text = new_raw_text
            else:
                node.raw_text = ""

            item.calculate_layout()
            item.update()
            self.update_links(item)

    def delete_node(self, node_data):
        to_remove = []
        for l_item in self.link_items:
            if (l_item.src_item.node_data.name == node_data.name or 
                l_item.dst_item.node_data.name == node_data.name):
                to_remove.append(l_item)
        for l in to_remove:
            self.delete_link(l)
        if node_data.name in self.node_items:
            item = self.node_items[node_data.name]
            self.scene.removeItem(item)
            del self.node_items[node_data.name]
        if node_data.name in self.nodes:
            del self.nodes[node_data.name]

    def recalc_connections(self):
        for node in self.nodes.values():
            node.connected_inputs.clear()
            node.connected_outputs.clear()
        
        for link in self.links:
            def get_label(raw):
                s = re.sub(r'\\\(.*?\\\)', '', raw)
                s = re.sub(r'<.*?>', '', s)
                return s.strip()

            if link.src_node in self.nodes:
                clean_src = get_label(link.src_pin)
                self.nodes[link.src_node].connected_outputs.add(clean_src)
            
            if link.dst_node in self.nodes:
                clean_dst = get_label(link.dst_pin)
                self.nodes[link.dst_node].connected_inputs.add(clean_dst)
        
        self.scene.update()

    def create_link(self, src_item, src_pin, dst_item, dst_pin):
        src_name = src_item.node_data.name
        dst_name = dst_item.node_data.name
        for l in self.links:
            if l.src_node == src_name and l.src_pin == src_pin and l.dst_node == dst_name and l.dst_pin == dst_pin:
                return
        link = LinkData(src_name, src_pin, dst_name, dst_pin)
        self.links.append(link)
        l_item = UELinkItem(src_item, src_pin, dst_item, dst_pin, self)
        self.scene.addItem(l_item)
        self.link_items.append(l_item)
        self.recalc_connections()

    def delete_link(self, link_item):
        self.scene.removeItem(link_item)
        if link_item in self.link_items:
            self.link_items.remove(link_item)
        src = link_item.src_item.node_data.name
        dst = link_item.dst_item.node_data.name
        spin = link_item.src_pin
        dpin = link_item.dst_pin
        self.links = [l for l in self.links if not (l.src_node == src and l.src_pin == spin and l.dst_node == dst and l.dst_pin == dpin)]
        self.recalc_connections()

    # ------------------- STANDARD LOGIC ------------------- #

    def load_graph_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Graph Text", "", "Text Files (*.txt)")
        if path: 
            self.load_graph_from_path(path)

    def load_graph_from_path(self, path):
        self.nodes.clear()
        self.links.clear()
        self.scene.clear()
        self.node_items.clear()
        self.link_items.clear()
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            self.parse_lines(lines)
            self.build_scene()
            self.recalc_connections()
            self.auto_sort_nodes() 
            self.center_viewport_on_nodes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse file: {e}")
    
    def handle_dropped_files(self, files):
        """Centralized logic for handling file drops."""
        for f in files:
            if f.endswith(".txt"):
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        content = file.read()
                except Exception as e:
                    print(f"Error reading file: {e}")
                    continue

                # Check for T3D Raw Text (Template Import)
                if "Begin Object" in content and "End Object" in content:
                    node_blocks = re.findall(r'(Begin Object.*?End Object)', content, re.DOTALL)
                    node_blocks = [b for b in node_blocks if "Class=/Script/UnrealEd.EdGraphNode_Comment" not in b]

                    if node_blocks:
                        self.update_template_library(node_blocks)
                
                # Otherwise, Load as Graph
                else:
                    self.load_graph_from_path(f)
                
                # Stop after the first valid text file
                break

    def export_graph_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph", "", "Text Files (*.txt)")
        if not path: return
        content = self.get_graph_string(include_coords=self.chk_coords.isChecked())
        
        with open(path, "w") as f: 
            f.write(content)
    
    def show_spec_dialog(self):
        # Use the dedicated SpecDialog (No buttons, no crash)
        dlg = SpecDialog(T("spec_text"), self)
        dlg.exec()

    def parse_lines(self, lines):
        link_pattern = re.compile(r'^\s*(.+)\s+\((.*?)\)\s*->\s*(.+)\s+\((.*?)\)\s*$')
        def_pattern = re.compile(r'^\s*(.+)\s+\((.*?)\)\s*:\s*\((.*?)\)\s*$')
        coord_pattern = re.compile(r'^\s*(.+)\s+\((-?\d+)\s*;\s*(-?\d+)\)\s*$')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"): continue
            
            # 1. Coordinates Logic
            coord_match = coord_pattern.match(line)
            if coord_match:
                name = coord_match.group(1).strip()
                x = int(coord_match.group(2))
                y = int(coord_match.group(3))

                self.ensure_node(name)
                self.nodes[name].x = x
                self.nodes[name].y = y
                continue

            # 2. Links logic
            link_match = link_pattern.match(line)
            if link_match:
                src_name = link_match.group(1).strip()
                src_pin = link_match.group(2).strip()
                dst_name = link_match.group(3).strip()
                dst_pin = link_match.group(4).strip()
                self.ensure_node(src_name)
                self.ensure_node(dst_name)
                self.nodes[src_name].add_output(src_pin)
                self.nodes[dst_name].add_input(dst_pin)
                self.links.append(LinkData(src_name, src_pin, dst_name, dst_pin))
                continue
            
            # 3. Definitions logic
            def_match = def_pattern.match(line)
            if def_match:
                name = def_match.group(1).strip()
                
                raw_ins = def_match.group(2) # e.g. "Return;;"
                ins = []
                if raw_ins:
                    # Logic: Split by semicolon. 
                    # If string ends with semicolon (which is the rule), split gives an empty string at the end.
                    # We remove that last empty string.
                    tokens = [x.strip() for x in raw_ins.split(';')]
                    if tokens and tokens[-1] == "":
                        tokens.pop() 
                    ins = tokens
                
                raw_outs = def_match.group(3)
                outs = []
                if raw_outs:
                    tokens = [x.strip() for x in raw_outs.split(';')]
                    if tokens and tokens[-1] == "":
                        tokens.pop()
                    outs = tokens
                
                self.ensure_node(name)
                for i in ins: self.nodes[name].add_input(i)
                for o in outs: self.nodes[name].add_output(o)
                continue

    def ensure_node(self, name):
        if name not in self.nodes:
            self.nodes[name] = NodeData(name)

    def add_node_visual(self, node):
        item = UENodeItem(node, self) 
        item.positionChanged.connect(self.update_links)
        self.scene.addItem(item)
        self.node_items[node.name] = item

    def build_scene(self):
        for name, node in self.nodes.items():
            self.add_node_visual(node)
        for link in self.links:
            if link.src_node in self.node_items and link.dst_node in self.node_items:
                src_item = self.node_items[link.src_node]
                dst_item = self.node_items[link.dst_node]
                link_item = UELinkItem(src_item, link.src_pin, dst_item, link.dst_pin, self)
                self.scene.addItem(link_item)
                self.link_items.append(link_item)

    def update_links(self, node_item):
        name = node_item.node_data.name
        for link_item in self.link_items:
            if link_item.src_item.node_data.name == name or link_item.dst_item.node_data.name == name:
                link_item.update_path()

    def auto_sort_subset(self, node_names, start_pos):
        """Sorts only the specified list of nodes using the same logic as global Auto Sort."""
        subset = set(node_names)
        if not subset: return

        # 1. Build Adjacency & Reverse Adjacency (Subset Only)
        adj = {n: [] for n in subset}
        rev_adj = {n: [] for n in subset} # Required for Barycentric sort (Parent tracking)
        in_degree = {n: 0 for n in subset}
        
        for link in self.links:
            if link.src_node in subset and link.dst_node in subset:
                adj[link.src_node].append(link.dst_node)
                rev_adj[link.dst_node].append(link.src_node)
                in_degree[link.dst_node] += 1
        
        # 2. Assign Layers (Topological Sort)
        layers = {}
        queue = [n for n in subset if in_degree[n] == 0]
        node_depth = {n: 0 for n in subset}
        
        visited = 0
        while queue:
            u = queue.pop(0)
            visited += 1
            d = node_depth[u]
            if d not in layers: layers[d] = []
            layers[d].append(u)
            
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    node_depth[v] = d + 1
                    queue.append(v)
        
        # Handle Cycles or Unreachable Islands
        if visited < len(subset):
            for n in subset:
                if n not in node_depth:
                    d = 0
                    node_depth[n] = d
                    if d not in layers: layers[d] = []
                    layers[d].append(n)

        # 3. Apply Positions (With Barycentric/Parent-Average Sorting)
        LAYER_X_GAP = 400 # Match the global sort gap
        NODE_Y_GAP = 30   
        
        current_x = start_pos.x()
        sorted_layers = sorted(layers.keys())
        
        for layer_idx in sorted_layers:
            nodes_in_layer = layers[layer_idx]
            
            # --- SAME LOGIC AS MAIN AUTO SORT ---
            def get_avg_parent_y(name):
                parents = rev_adj[name]
                if not parents:
                    # If no parents in subset, use alphanum stability or existing Y
                    return 0 
                
                # Calculate average Y of parents (who were placed in previous iterations)
                total_y = sum([self.nodes[p].y for p in parents])
                return total_y / len(parents)

            # Sort by parent position to minimize wire crossing
            nodes_in_layer.sort(key=get_avg_parent_y)
            # ------------------------------------

            current_y = start_pos.y()
            for name in nodes_in_layer:
                node = self.nodes[name]
                item = self.node_items.get(name)
                
                h = item.height if item else 100
                
                node.x = int(current_x)
                node.y = int(current_y)
                
                if item:
                    item.setPos(node.x, node.y)
                
                current_y += h + NODE_Y_GAP
            
            current_x += LAYER_X_GAP
            
        self.recalc_connections()

    def auto_sort_nodes(self):
        if not self.nodes: return
        
        # 1. Identify Islands
        components = self._get_connected_components()
        
        # Sort components: put largest ones first? or keep order?
        # Let's sort by the name of the 'first' node to keep it stable
        components.sort(key=lambda c: c[0].name)

        current_island_y = 50
        START_X = 50
        
        for island_nodes in components:
            # Layout this specific island
            island_height = self._layout_single_island(island_nodes, START_X, current_island_y)
            
            # Update cursor for next island
            current_island_y += island_height + 200 # Gap between execution chains

        self.recalc_connections()
        self.center_viewport_on_nodes()

    def _layout_single_island(self, nodes, start_x, start_y):
        """Lays out a specific set of nodes starting at start_y. Returns total height."""
        
        # --- CONFIG ---
        EXEC_Y_LEVEL = start_y      
        DATA_START_Y = start_y + 150
        MIN_X_PADDING = 80
        MIN_Y_PADDING = 40

        # 1. Calculate Ranks
        ranks = self._calculate_hybrid_ranks(nodes)
        
        if ranks:
            min_r = min(ranks.values())
            for n in ranks: ranks[n] -= min_r

        columns = {}
        for name, rank in ranks.items():
            if rank not in columns: columns[rank] = []
            columns[rank].append(self.nodes[name])

        # 2. Adaptive Column Widths
        col_start_x = {}
        current_x_cursor = start_x
        sorted_ranks = sorted(columns.keys())
        
        for rank in sorted_ranks:
            col_start_x[rank] = current_x_cursor
            max_w = 0
            for node in columns[rank]:
                item = self.node_items.get(node.name)
                w = item.width if item else 200
                if w > max_w: max_w = w
            current_x_cursor += max_w + MIN_X_PADDING

        # 3. Placement
        max_y_in_island = start_y
        
        for rank in sorted_ranks:
            col_nodes = columns[rank]
            col_execs = [n for n in col_nodes if n.is_exec_node()]
            col_data = [n for n in col_nodes if not n.is_exec_node()]
            
            # Execs
            exec_y_cursor = EXEC_Y_LEVEL
            col_execs.sort(key=lambda n: n.name)
            last_exec_bottom = EXEC_Y_LEVEL
            
            for node in col_execs:
                node.x = col_start_x[rank]
                node.y = exec_y_cursor
                item = self.node_items.get(node.name)
                h = item.height if item else 100
                
                exec_y_cursor += h + MIN_Y_PADDING + 20
                last_exec_bottom = node.y + h
                max_y_in_island = max(max_y_in_island, last_exec_bottom)

            # Data
            def get_data_sort_key(n):
                consumers = self._get_consumers(n)
                if not consumers: return 999999
                return sum([c.y for c in consumers]) / len(consumers)

            col_data.sort(key=get_data_sort_key)
            
            base_y = last_exec_bottom + 60 if col_execs else DATA_START_Y
            current_data_y = base_y
            
            for node in col_data:
                node.x = col_start_x[rank]
                consumers = self._get_consumers(node)
                if consumers:
                    target_y = sum([c.y for c in consumers]) / len(consumers)
                    node.y = max(current_data_y, target_y)
                else:
                    node.y = current_data_y
                
                item = self.node_items.get(node.name)
                h = item.height if item else 100
                current_data_y = node.y + h + MIN_Y_PADDING
                max_y_in_island = max(max_y_in_island, current_data_y)

        # 4. Local Visual Sync
        for n in nodes:
            if n.name in self.node_items:
                self.node_items[n.name].setPos(n.x, n.y)
        
        # 5. Local Collision Solve
        self._resolve_overlaps(nodes)
        
        # 6. Recalculate true max_y after collision solve
        final_max_y = start_y
        for n in nodes:
            item = self.node_items.get(n.name)
            h = item.height if item else 100
            if (n.y + h) > final_max_y:
                final_max_y = n.y + h
                
        # Update positions one last time
        for n in nodes:
            if n.name in self.node_items:
                self.node_items[n.name].setPos(n.x, n.y)

        return (final_max_y - start_y)
    
    # ------------------- FEATURE IMPL ------------------- #
    def delete_selection(self):
        """Feature 1: Delete selected nodes."""
        items = self.scene.selectedItems()
        nodes_to_delete = []
        # Gather nodes first (deleting links happens automatically in delete_node)
        for item in items:
            if isinstance(item, UENodeItem):
                nodes_to_delete.append(item.node_data)
        
        for node in nodes_to_delete:
            self.delete_node(node)

    def get_pin_guid_from_raw(self, raw_text, ui_pin_name, want_output):
        """Finds a Pin GUID by UI Name AND Direction."""
        lines = raw_text.split('\n')
        for line in lines:
            if "CustomProperties Pin" in line:
                name_match = re.search(r'PinName="([^"]+)"', line)
                if name_match:
                    raw_name = name_match.group(1)
                    
                    # 1. Check Direction First
                    is_line_output = 'Direction="EGPD_Output"' in line
                    if is_line_output != want_output:
                        continue 

                    # 2. Check Name Match
                    calculated_ui_name = get_pin_ui_name(raw_name, line)
                    if calculated_ui_name == ui_pin_name:
                        guid_match = re.search(r'PinId=([A-F0-9-]+)', line, re.IGNORECASE)
                        if guid_match:
                            return guid_match.group(1)
        return None

    def copy_selection(self):
        """Feature 2: Copy mixed content with FIXED Link Syntax."""
        items = self.scene.selectedItems()
        selected_nodes = [i.node_data for i in items if isinstance(i, UENodeItem)]
        
        if not selected_nodes:
            return
        
        has_error = False
        for i in items:
            if isinstance(i, UENodeItem):
                if not i.node_data.raw_text:
                    i.trigger_error()
                    has_error = True
                else:
                    i.hide_error()

        if has_error:
            self.show_flash_message(T("msg_copy_err"))

        final_output_parts = []
        
        # Group 1: Nodes WITH Raw Text (T3D)
        t3d_nodes = [n for n in selected_nodes if n.raw_text]
        if t3d_nodes:
            raw_texts = []
            selected_names = [n.name for n in t3d_nodes]
            
            for node in t3d_nodes:
                text = node.raw_text
                # Update Coordinates
                text = re.sub(r'NodePosX=(-?\d+)', f'NodePosX={int(node.x)}', text)
                text = re.sub(r'NodePosY=(-?\d+)', f'NodePosY={int(node.y)}', text)
                
                lines = text.split('\n')
                new_lines = []
                for line in lines:
                    if "CustomProperties Pin" in line:
                        is_output = "Direction=\"EGPD_Output\"" in line
                        
                        # 1. Strip existing links and closing syntax
                        line = re.sub(r',?\s*LinkedTo=\([^\)]+\)', '', line)
                        line = line.rstrip()
                        if line.endswith(",)"): line = line[:-2]
                        elif line.endswith(")"): line = line[:-1]
                        
                        # 2. Find connections
                        name_m = re.search(r'PinName="([^"]+)"', line)
                        valid_links = []
                        
                        if name_m:
                            raw_p = name_m.group(1)
                            ui_p = get_pin_ui_name(raw_p, line)
                            
                            for link in self.links:
                                target_node = None
                                target_pin = None
                                
                                # Check if connected node is ALSO in selection
                                if is_output and link.src_node == node.name and link.src_pin == ui_p:
                                    if link.dst_node in selected_names:
                                        target_node = self.nodes[link.dst_node]
                                        target_pin = link.dst_pin
                                        want_out = False
                                elif not is_output and link.dst_node == node.name and link.dst_pin == ui_p:
                                    if link.src_node in selected_names:
                                        target_node = self.nodes[link.src_node]
                                        target_pin = link.src_pin
                                        want_out = True
                                        
                                if target_node:
                                    tgt_guid = self.get_pin_guid_from_raw(target_node.raw_text, target_pin, want_out)
                                    if tgt_guid:
                                        valid_links.append(f"{target_node.internal_name} {tgt_guid}")
                            
                        # 3. Append Links if found
                        if valid_links:
                            joined = ",".join(valid_links)
                            line += f",LinkedTo=({joined})"
                        
                        # 4. Close line
                        line += ",)"
                        
                    new_lines.append(line)
                raw_texts.append("\n".join(new_lines))
            final_output_parts.append("\n".join(raw_texts))

        # Group 2: Simplified Nodes
        simple_nodes = [n for n in selected_nodes if not n.raw_text]
        if simple_nodes:
            lines = ["# --- Copied Simplified Nodes ---", "# Node Definitions"]
            for n in simple_nodes:
                ins = n.exec_in_pins + n.data_inputs
                outs = n.exec_out_pins + n.data_outputs
                lines.append(f"{n.name} ({'; '.join(ins)}) : ({'; '.join(outs)})")
            
            lines.append("# Links")
            selected_names_set = {n.name for n in selected_nodes}
            for link in self.links:
                if link.src_node in selected_names_set and link.dst_node in selected_names_set:
                    is_src_simple = link.src_node in [sn.name for sn in simple_nodes]
                    is_dst_simple = link.dst_node in [sn.name for sn in simple_nodes]
                    if is_src_simple or is_dst_simple:
                        lines.append(f"{link.src_node} ({link.src_pin}) -> {link.dst_node} ({link.dst_pin})")

            lines.append("# Coordinates")
            for n in simple_nodes:
                lines.append(f"{n.name} ({int(n.x)}; {int(n.y)})")
            
            final_output_parts.append("\n".join(lines))

        QApplication.clipboard().setText("\n\n".join(final_output_parts))

    def freshen_raw_template(self, raw_text, new_internal_name):
        """
        Takes a raw T3D block, generates new GUIDs for Node and Pins, 
        and updates the Internal Name to ensure uniqueness.
        """
        # 1. Generate new Node GUID
        new_node_guid = uuid.uuid4().hex.upper()
        raw_text = re.sub(r'NodeGuid=[A-F0-9-]+', f'NodeGuid={new_node_guid}', raw_text, flags=re.IGNORECASE)

        # 2. Update Internal Name
        # We replace Name="OldName" and references like 'OldName'
        old_name_match = re.search(r'Name="([^"]+)"', raw_text)
        if old_name_match:
            old_name = old_name_match.group(1)
            raw_text = raw_text.replace(f'Name="{old_name}"', f'Name="{new_internal_name}"')
            raw_text = raw_text.replace(f'.{old_name}\'', f'.{new_internal_name}\'')
            raw_text = raw_text.replace(f':{old_name}\'', f':{new_internal_name}\'')

        # 3. Regenerate Pin IDs
        # We must find all PinIds and map them to new UUIDs to avoid conflicts
        pin_id_map = {}
        all_pin_ids = re.findall(r'PinId=([A-F0-9-]+)', raw_text, flags=re.IGNORECASE)
        for old_id in all_pin_ids:
            if old_id not in pin_id_map:
                pin_id_map[old_id] = uuid.uuid4().hex.upper()
        
        for old_id, new_id in pin_id_map.items():
            raw_text = raw_text.replace(f'PinId={old_id}', f'PinId={new_id}')

        # 4. Clear LinkedTo (Simplified Paste logic will rebuild these based on visual links)
        # We strip existing links so they don't ghost connect to non-existent nodes
        raw_text = re.sub(r',?\s*LinkedTo=\([^\)]+\)', '', raw_text)

        return raw_text

    def paste_from_clipboard(self, target_pos):
        """Feature 3: Smart Paste handling both T3D (Append) and Simplified (Append w/ Rename)."""
        text = QApplication.clipboard().text()
        if not text: return
        
        # [REMOVED] Marker Filtering Block (Output Text Starts/Ends) is deleted here.
        # The parser loops below automatically skip lines starting with '#' so explicit filtering isn't needed.

        # ==========================================
        # CASE 1: T3D RAW TEXT (Has Begin Object)
        # ==========================================
        if "Begin Object" in text:
            node_blocks = re.findall(r'(Begin Object.*?End Object)', text, re.DOTALL)
            
            # --- Filter out Comment Nodes immediately ---
            node_blocks = [b for b in node_blocks if "Class=/Script/UnrealEd.EdGraphNode_Comment" not in b]
            
            if not node_blocks: return

            # --- PREPARATION & MAPPING ---
            existing_internals = {n.internal_name for n in self.nodes.values()}
            existing_visuals = set(self.nodes.keys())

            raw_rename_map = {}  # Old_Internal_Name -> New_Internal_Name
            guid_map = {}        # Old_Node_Guid -> New_Node_Guid
            pin_id_map = {}      # Old_Pin_Guid -> New_Pin_Guid
            
            min_x = float('inf')
            min_y = float('inf')
            temp_pos = [] 

            # --- PASS 1: Generate Mappings (Names, NodeGuids, PinIds) ---
            for block in node_blocks:
                # 1. Position Calc
                x_match = re.search(r'NodePosX=(-?\d+)', block)
                y_match = re.search(r'NodePosY=(-?\d+)', block)
                x = int(x_match.group(1)) if x_match else 0
                y = int(y_match.group(1)) if y_match else 0
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                temp_pos.append((x, y))

                # 2. Internal Name Resolution
                name_match = re.search(r'Name="([^"]+)"', block)
                old_internal = name_match.group(1) if name_match else "Unknown"

                if old_internal in existing_internals:
                    # Collision detected: Find Max Suffix
                    match = re.match(r'^(.*_)(\d+)$', old_internal)
                    base_prefix = match.group(1) if match else (old_internal + "_")

                    max_suffix = 0
                    for existing in existing_internals:
                        if existing.startswith(base_prefix):
                            suffix_part = existing[len(base_prefix):]
                            if suffix_part.isdigit():
                                val = int(suffix_part)
                                if val > max_suffix: max_suffix = val
                    
                    cnt = max_suffix + 1
                    new_internal = f"{base_prefix}{cnt}"
                    while new_internal in existing_internals:
                        cnt += 1
                        new_internal = f"{base_prefix}{cnt}"
                    
                    raw_rename_map[old_internal] = new_internal
                    existing_internals.add(new_internal) 
                else:
                    raw_rename_map[old_internal] = old_internal
                    existing_internals.add(old_internal)

                # 3. NodeGuid Mapping
                guid_match = re.search(r'NodeGuid=([A-F0-9-]+)', block, re.IGNORECASE)
                if guid_match:
                    guid_map[guid_match.group(1)] = uuid.uuid4().hex.upper()

                # 4. PinId Mapping
                all_pin_ids = re.findall(r'PinId=([A-F0-9-]+)', block, re.IGNORECASE)
                for old_pid in all_pin_ids:
                    if old_pid not in pin_id_map:
                        pin_id_map[old_pid] = uuid.uuid4().hex.upper()

            # --- PASS 2: Rewrite Raw Text ---
            final_blocks = []
            
            for i, block in enumerate(node_blocks):
                # A. Replace Name
                nm_match = re.search(r'Name="([^"]+)"', block)
                if not nm_match: continue
                old_internal = nm_match.group(1)
                new_internal = raw_rename_map.get(old_internal, old_internal)
                
                if new_internal != old_internal:
                    block = block.replace(f'Name="{old_internal}"', f'Name="{new_internal}"')
                    block = block.replace(f'.{old_internal}\'', f'.{new_internal}\'')
                    block = block.replace(f':{old_internal}\'', f':{new_internal}\'')

                # B. Replace NodeGuid
                gm_match = re.search(r'NodeGuid=([A-F0-9-]+)', block, re.IGNORECASE)
                if gm_match and gm_match.group(1) in guid_map:
                    block = block.replace(gm_match.group(1), guid_map[gm_match.group(1)])

                # C. Replace PinIds
                for old_pid, new_pid in pin_id_map.items():
                    block = block.replace(f'PinId={old_pid}', f'PinId={new_pid}')

                # D. Update Position
                orig_x, orig_y = temp_pos[i]
                if min_x == float('inf'): min_x = orig_x
                if min_y == float('inf'): min_y = orig_y
                final_x = int(target_pos.x() + (orig_x - min_x))
                final_y = int(target_pos.y() + (orig_y - min_y))
                block = re.sub(r'NodePosX=(-?\d+)', f'NodePosX={final_x}', block)
                block = re.sub(r'NodePosY=(-?\d+)', f'NodePosY={final_y}', block)

                # E. Fix Links (LinkedTo)
                lines = block.split('\n')
                new_lines = []
                for line in lines:
                    if "LinkedTo=" in line:
                        link_match = re.search(r'LinkedTo=\(([^)]+)\)', line)
                        if link_match:
                            raw_links = [x.strip() for x in link_match.group(1).split(',')]
                            valid_links = []
                            for entry in raw_links:
                                parts = entry.split()
                                if not parts: continue
                                
                                tgt_old_name = parts[0]
                                tgt_old_pin_guid = parts[1] if len(parts) > 1 else ""
                                
                                if tgt_old_name in raw_rename_map:
                                    new_tgt_name = raw_rename_map[tgt_old_name]
                                    new_tgt_pin_guid = pin_id_map.get(tgt_old_pin_guid, tgt_old_pin_guid)
                                    valid_links.append(f"{new_tgt_name} {new_tgt_pin_guid}")
                            
                            if valid_links:
                                joined = ",".join(valid_links)
                                line = line.replace(link_match.group(0), f"LinkedTo=({joined})")
                            else:
                                line = re.sub(r',?\s*LinkedTo=\([^)]+\)', '', line)
                    new_lines.append(line)
                
                final_blocks.append("\n".join(new_lines))

            # --- PASS 3: Create Visual Nodes & Save Templates ---
            self.scene.clearSelection()
            internal_to_visual = {} 

            for block in final_blocks:
                data = get_node_data(block)
                
                # Visual Name Resolution
                base_visual = data['type'] 
                
                # --- NEW: Store Template with Type-Aware Key ---
                # 1. Clean the visual name (remove _Num)
                base_visual_key = re.sub(r'_\d+$', '', data['type']).strip()

                # 2. Detect Type (Func/Event)
                c_match = re.search(r'Class=[\w\./]+\.([^ "\']+)', block)
                c_name = c_match.group(1) if c_match else ""
                
                t_suffix = "FUNC"
                if "K2Node_CustomEvent" in c_name or "K2Node_Event" in c_name:
                    t_suffix = "EVT"
                
                key = f"{base_visual_key}::{t_suffix}"
                
                # [FIXED] Only save if it doesn't exist to prevent overwriting "Golden" templates
                if key not in self.raw_node_templates:
                    self.raw_node_templates[key] = block
                # ------------------------------------------------
                
                match_v = re.match(r'^(.*_)(\d+)$', base_visual)
                base_v_prefix = match_v.group(1) if match_v else (re.sub(r'_\d+$', '', base_visual) + "_")

                max_v_suffix = 0
                for v_name in existing_visuals:
                    if v_name.startswith(base_v_prefix):
                        suffix_part = v_name[len(base_v_prefix):]
                        if suffix_part.isdigit():
                            val = int(suffix_part)
                            if val > max_v_suffix: max_v_suffix = val
                
                cnt = max_v_suffix + 1
                visual_name = f"{base_v_prefix}{cnt}"
                while visual_name in existing_visuals:
                    cnt += 1
                    visual_name = f"{base_v_prefix}{cnt}"
                
                existing_visuals.add(visual_name)
                internal_to_visual[data['id']] = visual_name
                
                new_node = NodeData(visual_name)
                new_node.internal_name = data['id']
                new_node.raw_text = block
                new_node.x = data['x']
                new_node.y = data['y']
                
                for p in data['pins']:
                    pin_str = p['name']
                    # Append value if it exists and it's an input without a link
                    if p['dir'] == "IN" and p['value'] and not p['links']:
                         pin_str = f"{p['name']}\\({p['value']}\\)"

                    if p.get('category') == 'exec':
                        if p['dir'] == "IN": 
                            new_node.exec_in_pins.append(pin_str)
                        else: 
                            new_node.exec_out_pins.append(pin_str)
                    else:
                        if p['dir'] == "IN": new_node.add_input(pin_str)
                        else: new_node.add_output(pin_str)
                    
                self.nodes[visual_name] = new_node
                self.add_node_visual(new_node)
                
                if visual_name in self.node_items:
                    self.node_items[visual_name].setSelected(True)
            
            self.save_templates_to_disk()

            # --- PASS 4: Rebuild Visual Links ---
            for block in final_blocks:
                src_data = get_node_data(block)
                src_visual = internal_to_visual.get(src_data['id'])
                if not src_visual: continue

                for p in src_data['pins']:
                    if p['dir'] == 'OUT' and p['links']:
                        for link_info in p['links']:
                            tgt_internal = link_info['node'] 
                            tgt_pin_guid = link_info['pin_guid'] 
                            
                            tgt_visual = internal_to_visual.get(tgt_internal)
                            
                            if tgt_visual and tgt_visual in self.nodes:
                                tgt_node = self.nodes[tgt_visual]
                                
                                tgt_temp_data = get_node_data(tgt_node.raw_text)
                                tgt_pin_name = "Unknown"
                                for tp in tgt_temp_data['pins']:
                                    if tp['guid'] == tgt_pin_guid:
                                        tgt_pin_name = tp['name']
                                        break
                                
                                if tgt_pin_name != "Unknown":
                                    self.create_link(
                                        self.node_items[src_visual], p['name'], 
                                        self.node_items[tgt_visual], tgt_pin_name
                                    )

            self.recalc_connections()
            self.show_flash_message(T("msg_pasted").format(len(final_blocks)))
            return

        # ==========================================
        # CASE 2: SIMPLIFIED TEXT (Append Mode)
        # ==========================================
        
        # 1. Parse Text into Temp Structures
        temp_nodes = {}
        temp_links = []
        temp_coords = {}
        
        lines = text.split('\n')
        
        link_pattern = re.compile(r'^\s*(.+)\s+\((.*?)\)\s*->\s*(.+)\s+\((.*?)\)\s*$')
        def_pattern = re.compile(r'^\s*(.+)\s+\((.*?)\)\s*:\s*\((.*?)\)\s*$')
        coord_pattern = re.compile(r'^\s*(.+)\s+\((-?\d+)\s*;\s*(-?\d+)\)\s*$')

        min_x = float('inf')
        min_y = float('inf')

        for line in lines:
            line = line.strip()
            # Loop already handles skipping comments
            if not line or line.startswith("#"): continue
            
            # Coords
            cm = coord_pattern.match(line)
            if cm:
                name = cm.group(1).strip()
                x, y = int(cm.group(2)), int(cm.group(3))
                temp_coords[name] = (x, y)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                continue
            
            # Links
            lm = link_pattern.match(line)
            if lm:
                temp_links.append({
                    "src": lm.group(1).strip(), "src_pin": lm.group(2).strip(),
                    "dst": lm.group(3).strip(), "dst_pin": lm.group(4).strip()
                })
                continue
            
            # Definitions
            dm = def_pattern.match(line)
            if dm:
                name = dm.group(1).strip()
                if name not in temp_nodes:
                    temp_nodes[name] = NodeData(name)
                
                raw_ins = dm.group(2)
                if raw_ins:
                    tokens = [x.strip() for x in raw_ins.split(';')]
                    if tokens and tokens[-1] == "":
                        tokens.pop() 
                    for i in tokens: temp_nodes[name].add_input(i)
                
                raw_outs = dm.group(3)
                if raw_outs:
                    tokens = [x.strip() for x in raw_outs.split(';')]
                    if tokens and tokens[-1] == "":
                        tokens.pop()
                    for o in tokens: temp_nodes[name].add_output(o)

        if not temp_nodes: return

        # 2. Resolve Naming Collisions & Calculate Offset
        if min_x == float('inf'): min_x, min_y = 0, 0 
        
        rename_map = {} 
        existing_names = set(self.nodes.keys())
        existing_internals = {n.internal_name for n in self.nodes.values()}
        
        self.scene.clearSelection()

        for old_name, node in temp_nodes.items():
            # Apply Coordinates
            if old_name in temp_coords:
                ox, oy = temp_coords[old_name]
                node.x = int(target_pos.x() + (ox - min_x))
                node.y = int(target_pos.y() + (oy - min_y))
            else:
                # Default relative layout
                node.x = int(target_pos.x())
                node.y = int(target_pos.y())

            # Rename Logic
            base_name = old_name
            m = re.match(r'^(.*)_\d+$', old_name)
            if m: base_name = m.group(1)
            
            new_name = old_name
            if new_name in existing_names:
                max_suffix = 0
                prefix = base_name + "_"
                for existing in existing_names:
                    if existing.startswith(prefix):
                        suffix = existing[len(prefix):]
                        if suffix.isdigit():
                            max_suffix = max(max_suffix, int(suffix))
                new_name = f"{prefix}{max_suffix + 1}"
            
            rename_map[old_name] = new_name
            node.name = new_name
            existing_names.add(new_name)
            
            # 1. Determine base visual name (e.g. "PrintString")
            base_visual_key = re.sub(r'_\d+$', '', new_name).strip()
            norm_base = base_visual_key.lower().replace(" ", "") # Normalize: "printstring"
            
            # 2. Gather Candidates (Ignore spaces in keys)
            candidates = []
            for k in self.raw_node_templates:
                if "::" in k:
                    visual_part = k.split("::")[0]
                    norm_cand = visual_part.lower().replace(" ", "") # Normalize: "printstring"
                    
                    # Check exact match or context prefix match
                    if norm_cand == norm_base or norm_cand.startswith(f"{norm_base}("):
                        candidates.append(k)

            best_template_key = None
            
            if not candidates:
                # Fallback
                t_suffix = "FUNC" if (node.exec_in_pins or not node.exec_out_pins) else "EVT"
                fallback_key = f"{base_visual_key}::{t_suffix}"
                if fallback_key in self.raw_node_templates:
                    best_template_key = fallback_key
            else:
                # 3. Disambiguate using Pin Names
                target_pins = set()
                for p in (node.exec_in_pins + node.exec_out_pins + node.data_inputs + node.data_outputs):
                    # Use global parser to get clean label
                    label, _, _, _ = parse_pin_text(p)
                    target_pins.add(label.replace(" ", ""))

                best_score = -1
                
                for cand_key in candidates:
                    raw_t3d = self.raw_node_templates[cand_key]
                    cand_pins = set()
                    lines = raw_t3d.split('\n')
                    for line in lines:
                        if "CustomProperties Pin" in line:
                            name_m = re.search(r'PinName="([^"]+)"', line)
                            if name_m:
                                ui_name = get_pin_ui_name(name_m.group(1), line)
                                cand_pins.add(ui_name.replace(" ", ""))
                    
                    score = len(target_pins.intersection(cand_pins))
                    
                    # Tie-breaker
                    if score > best_score:
                        best_score = score
                        best_template_key = cand_key
                    elif score == best_score:
                        if "Kismet" in cand_key: 
                            best_template_key = cand_key

            # 4. Apply Template & Sync Values
            if best_template_key and best_template_key in self.raw_node_templates:
                template_text = self.raw_node_templates[best_template_key]
                
                # Generate new internal name
                class_match = re.search(r'Class=[\w\./]+\.([^ "\']+)', template_text)
                class_prefix = class_match.group(1) if class_match else "Node"
                
                int_cnt = 1
                new_internal = f"{class_prefix}_{int_cnt}"
                while new_internal in existing_internals:
                    int_cnt += 1
                    new_internal = f"{class_prefix}_{int_cnt}"
                existing_internals.add(new_internal)

                # Inject Template
                node.raw_text = self.freshen_raw_template(template_text, new_internal)
                node.internal_name = new_internal
                
                # [NEW] SYNC VALUES: Update Raw Text with Pasted Values (e.g. "Hiiiiii")
                # This ensures the Raw Text matches the Visual Node immediately
                
                # Sync Inputs
                for p_str in node.data_inputs:
                    label, val, has_val, _ = parse_pin_text(p_str)
                    if has_val:
                        updated = update_raw_block_value(node.raw_text, label, val, is_input=True)
                        if updated: node.raw_text = updated

                # Sync Outputs (if any have values)
                for p_str in node.data_outputs:
                    label, val, has_val, _ = parse_pin_text(p_str)
                    if has_val:
                        updated = update_raw_block_value(node.raw_text, label, val, is_input=False)
                        if updated: node.raw_text = updated
            # --------------------------------------------------
            
            self.nodes[new_name] = node
            self.add_node_visual(node)
            if new_name in self.node_items:
                self.node_items[new_name].setSelected(True)

        # 3. Rebuild Links with New Names
        for link in temp_links:
            src_old = link["src"]
            dst_old = link["dst"]
            
            src_new = rename_map.get(src_old, src_old)
            dst_new = rename_map.get(dst_old, dst_old)
            
            if src_new in self.nodes and dst_new in self.nodes:
                if src_new in self.node_items and dst_new in self.node_items:
                    self.create_link(
                        self.node_items[src_new], link["src_pin"],
                        self.node_items[dst_new], link["dst_pin"]
                    )

        if not temp_coords:
            self.auto_sort_subset(list(rename_map.values()), target_pos)
        self.recalc_connections()
        self.show_flash_message(T("msg_pasted").format(len(temp_nodes)))

    def closeEvent(self, event):
        # 1. Check if cleanup is already running
        if getattr(self, "_is_cleaning_up", False):
            event.accept()
            return

        # 2. Visually "close" immediately
        self.hide()
        
        # 3. Set flag and ignore the immediate close
        self._is_cleaning_up = True
        event.ignore()

        # 4. Background Cleanup Task
        def cleanup_task():
            try:
                # Run the new simple cleaner
                cleanup_nodeue_data()
            except Exception as e:
                print(f"Cleanup error: {e}")
            finally:
                QApplication.instance().quit()

        # 5. Start Thread
        import threading
        t = threading.Thread(target=cleanup_task, daemon=True)
        t.start()

def cleanup_nodeue_data():

    try:
        base_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'NodeUE')
        if not os.path.exists(base_dir):
            return

        keep_files = ["Config.json", "Templates.json"]

        print(f"Cleaning storage: {base_dir}")

        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            
            # Rule 1: Always keep Config and Templates (Files in root)
            if item in keep_files:
                continue

            # Rule 2: Handle Folders
            if os.path.isdir(item_path):
                try:
                    # --- STRICT CHECK START ---
                    expected_json_path = os.path.join(item_path, f"{item}.json")
                    
                    if os.path.exists(expected_json_path):
                        # It has the matching file. It is a valid blueprint. Keep it.
                        continue
                    else:
                        # It is empty OR contains mismatching files. Delete it.
                        print(f"Deleting invalid folder (No matching json): {item}")
                        shutil.rmtree(item_path)
                    # --- STRICT CHECK END ---
                    
                except Exception as e:
                    print(f"Error checking folder {item}: {e}")
            
            # Rule 3: Handle loose files in root (Junk that isn't Config/Templates)
            else:
                try:
                    print(f"Deleting junk file: {item}")
                    os.remove(item_path)
                except Exception as e:
                    print(f"Error deleting file {item}: {e}")

    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":

    app = QApplication(sys.argv)
    
    app.setDesktopFileName('NodeUE.UE5.Blueprint.Viewer')
    app.setWindowIcon(QIcon(resource_path("app_icon.ico")))
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = UEGraphApp()
    window.show()
    sys.exit(app.exec())
