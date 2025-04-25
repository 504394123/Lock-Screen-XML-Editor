import sys
import os
import copy
import json
import re
import io
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QTableWidget, 
                           QTableWidgetItem, QPushButton, QMenu, QAction, QMessageBox,
                           QInputDialog, QFileDialog, QLabel, QHeaderView, QAbstractItemView,
                           QToolBar, QLineEdit, QDialog, QScrollArea, QCheckBox, QListWidget,
                           QDialogButtonBox, QListWidgetItem, QGridLayout, QTabWidget,
                           QCompleter, QStyledItemDelegate, QAbstractItemView)
from PyQt5.QtCore import (Qt, QMimeData, QModelIndex, QSize, QTimer, QStringListModel,
                         QFileSystemWatcher)
from PyQt5.QtGui import (QDrag, QFont, QColor, QSyntaxHighlighter, QTextCharFormat, 
                        QPixmap, QTextCursor, QIcon, QTextFormat)
from lxml import etree
from xml_tree_editor import XMLTreeWidget, DraggableTreeItem
from xml_snippet_library import XMLSnippetLibrary
from tree_state_manager import TreeStateManager

class GlobalAttributes:
    def __init__(self):
        self.feature_comments = {}  # 功能注释: {element_name: comment}
        self.attribute_comments = {}  # 属性注释: {attribute_name: comment}
        
        # 加载已保存的注释
        self.load_comments()
    
    def load_comments(self):
        try:
            if os.path.exists('feature_comments.json'):
                with open('feature_comments.json', 'r', encoding='utf-8') as f:
                    self.feature_comments = json.load(f)
            
            if os.path.exists('attribute_comments.json'):
                with open('attribute_comments.json', 'r', encoding='utf-8') as f:
                    self.attribute_comments = json.load(f)
        except Exception as e:
            print(f"加载注释失败: {e}")
    
    def save_comments(self):
        try:
            with open('feature_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.feature_comments, f, ensure_ascii=False, indent=2)
            
            with open('attribute_comments.json', 'w', encoding='utf-8') as f:
                json.dump(self.attribute_comments, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存注释失败: {e}")

class XMLHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(XMLHighlighter, self).__init__(parent)
        
        self.highlighting_rules = []
        
        # XML标签
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#00008B"))  # 深蓝色
        # 高亮<tag></tag>
        self.highlighting_rules.append((re.compile(r"<[^>]*>"), tag_format))
        
        # 属性
        attr_format = QTextCharFormat()
        attr_format.setForeground(QColor("#8B0000"))  # 深红色
        # 高亮属性名（name=value中的name部分）
        self.highlighting_rules.append((re.compile(r"\s+([a-zA-Z_][a-zA-Z0-9_\-]*)="), attr_format))
        
        # 属性值
        attr_value_format = QTextCharFormat()
        attr_value_format.setForeground(QColor("#006400"))  # 深绿色
        # 高亮属性值（name="value"中的"value"部分）
        self.highlighting_rules.append((re.compile(r"=\"([^\"]*)\"|='([^']*)'"), attr_value_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))  # 灰色
        # 高亮注释
        self.highlighting_rules.append((re.compile(r"<!--[^<]*-->"), comment_format))
    
    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

class AttributeCompleterDelegate(QStyledItemDelegate):
    """
    表格单元格编辑器代理，提供自动补全功能
    """
    def __init__(self, parent=None, attr_completer=None, value_completer=None, enabled=True):
        super(AttributeCompleterDelegate, self).__init__(parent)
        self.attr_completer = attr_completer  # 属性名补全器
        self.value_completer = value_completer  # 属性值补全器
        self.enabled = enabled  # 是否启用自动补全
    
    def createEditor(self, parent, option, index):
        try:
            # 创建自定义编辑器
            if index.column() == 1 and self.value_completer and self.enabled:  # 属性值列，使用自定义编辑器
                editor = CustomLineEdit(parent)
                
                # 使用异常处理包装设置补全器
                try:
                    editor.setCustomCompleter(self.value_completer)
                    
                    # 连接文本变化信号，用于调试
                    editor.textChanged.connect(lambda text: print(f"编辑文本: {text}"))
                    
                    # 处理编辑器销毁信号
                    editor.destroyed.connect(lambda: print("编辑器已销毁"))
                except Exception as e:
                    print(f"设置补全器时发生错误: {e}")
                
                return editor
            else:  # 其他列使用标准编辑器
                editor = QLineEdit(parent)
                
                # 如果禁用了自动补全，直接返回编辑器
                if not self.enabled:
                    return editor
                
                # 属性名列使用标准QCompleter
                if index.column() == 0 and self.attr_completer:
                    try:
                        editor.setCompleter(self.attr_completer)
                    except Exception as e:
                        print(f"设置属性名补全器时发生错误: {e}")
            
            return editor
        except Exception as e:
            print(f"创建编辑器时发生错误: {e}")
            # 出错时返回一个基本的编辑器，确保不会崩溃
            return QLineEdit(parent)
    
    def setEditorData(self, editor, index):
        """
        将模型数据设置到编辑器中
        """
        try:
            # 获取模型中的值
            value = index.data(Qt.EditRole)
            if value is not None:
                # 设置编辑器文本
                editor.setText(str(value))
        except Exception as e:
            print(f"设置编辑器数据时发生错误: {e}")
    
    def setModelData(self, editor, model, index):
        """
        将编辑器数据设置到模型中
        """
        try:
            # 获取编辑器文本
            value = editor.text()
            # 设置模型数据
            model.setData(index, value, Qt.EditRole)
        except Exception as e:
            print(f"设置模型数据时发生错误: {e}")
    
    def updateEditorGeometry(self, editor, option, index):
        """
        更新编辑器几何形状
        """
        try:
            # 使编辑器填充单元格
            editor.setGeometry(option.rect)
        except Exception as e:
            print(f"更新编辑器几何形状时发生错误: {e}")

class AttributeCompleter:
    """
    属性自动补全管理器，负责收集补全数据和创建补全器
    """
    def __init__(self):
        # 预定义的常用XML属性名列表
        self.predefined_attributes = [
            "id", "name", "class", "type", "value", "src", "href", "style", 
            "width", "height", "alt", "title", "target", "rel", "action",
            "method", "data", "lang", "dir", "checked", "selected", "disabled",
            "readonly", "maxlength", "size", "placeholder", "pattern", "min", 
            "max", "step", "required", "multiple", "autoplay", "controls",
            "loop", "muted", "preload", "colspan", "rowspan", "headers",
            "scope", "xmlns", "xmlns:xsi", "xsi:schemaLocation", "version",
            "encoding", "standalone", "x", "y", "z", "transform", "viewBox",
            "fill", "stroke", "stroke-width", "d", "points", "cx", "cy", "r",
            "rx", "ry", "x1", "y1", "x2", "y2", "offset", "stop-color",
            "font-family", "font-size", "font-weight", "text-anchor",
            "alignment-baseline", "background", "color", "border", "margin",
            "padding", "display", "position", "top", "right", "bottom", "left",
            "float", "clear", "overflow", "z-index", "opacity"
        ]
        
        # 用户自定义的属性名列表
        self.custom_attributes = []
        
        # 加载自定义属性
        self.load_custom_attributes()
        
        # 属性值字典，键为属性名，值为该属性的所有可能值列表
        self.attribute_values = {}
        
        # 初始化引用变量集合
        self.referenced_vars = set()
        
        # 创建属性名补全器（使用默认QCompleter就足够了）
        self.attr_completer = QCompleter(self.get_attribute_list())
        self.attr_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.attr_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.attr_completer.setFilterMode(Qt.MatchStartsWith)
        
        # 创建属性值补全器（使用自定义CustomCompleter）
        self.value_completer = CustomCompleter([])
        
        # 当前正在编辑的属性名
        self.current_attribute = ""
    
    def load_custom_attributes(self):
        """
        从配置文件加载自定义属性名列表
        """
        try:
            if os.path.exists('custom_attributes.json'):
                with open('custom_attributes.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.custom_attributes = data.get('attributes', [])
        except Exception as e:
            print(f"加载自定义属性列表失败: {e}")
            self.custom_attributes = []
    
    def save_custom_attributes(self):
        """
        保存自定义属性名列表到配置文件
        """
        try:
            with open('custom_attributes.json', 'w', encoding='utf-8') as f:
                json.dump({'attributes': self.custom_attributes}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自定义属性列表失败: {e}")
    
    def add_custom_attribute(self, attribute):
        """
        添加自定义属性名
        """
        if attribute and attribute not in self.custom_attributes and attribute not in self.predefined_attributes:
            self.custom_attributes.append(attribute)
            self.custom_attributes.sort()
            self.save_custom_attributes()
            # 更新属性补全器
            self.attr_completer.setModel(QStringListModel(self.get_attribute_list()))
            return True
        return False
    
    def remove_custom_attribute(self, attribute):
        """
        删除自定义属性名
        """
        if attribute in self.custom_attributes:
            self.custom_attributes.remove(attribute)
            self.save_custom_attributes()
            # 更新属性补全器
            self.attr_completer.setModel(QStringListModel(self.get_attribute_list()))
            return True
        return False
    
    def get_attribute_list(self):
        """
        获取完整的属性名列表（预定义+自定义）
        """
        # 打印当前的属性列表
        print(f"预定义属性: {len(self.predefined_attributes)}, 自定义属性: {len(self.custom_attributes)}")
        
        # 合并预定义和自定义属性列表
        combined = sorted(set(self.predefined_attributes + self.custom_attributes))
        print(f"合并后的属性总数: {len(combined)}")
        
        return combined
    
    def extract_attribute_values(self, xml_root):
        """
        从XML文档中提取所有属性值和引用变量(支持#和@前缀)
        
        Args:
            xml_root: XML文档的根元素
        """
        self.attribute_values = {}
        self.referenced_vars = set()  # 存储所有被引用的变量名
        
        def process_element(element):
            # 遍历元素的所有属性
            for attr_name, attr_value in element.attrib.items():
                # 保存完整的属性值
                if attr_name not in self.attribute_values:
                    self.attribute_values[attr_name] = set()
                self.attribute_values[attr_name].add(attr_value)
                
                # 提取name属性的值（供引用使用）
                if attr_name == "name":
                    self.referenced_vars.add(attr_value)
                
                # 从属性值中提取所有引用的变量名
                # 提取#引用
                if "#" in attr_value:
                    var_refs = re.findall(r'#([a-zA-Z0-9_]+)', attr_value)
                    for var_name in var_refs:
                        self.referenced_vars.add(var_name)
                
                # 提取@引用
                if "@" in attr_value:
                    var_refs = re.findall(r'@([a-zA-Z0-9_]+)', attr_value)
                    for var_name in var_refs:
                        self.referenced_vars.add(var_name)
            
            # 递归处理子元素
            for child in element:
                process_element(child)
        
        # 从根元素开始递归处理
        if xml_root is not None:
            process_element(xml_root)
            print(f"从XML中提取了{len(self.referenced_vars)}个引用变量")
    
    def update_value_completer(self, attribute_name):
        """
        根据当前属性名更新值补全器
        
        Args:
            attribute_name: 当前编辑的属性名
        """
        self.current_attribute = attribute_name
        values = list(self.attribute_values.get(attribute_name, set()))
        
        # 对于所有属性，添加引用变量(#和@前缀)
        hash_values = []
        at_values = []
        if hasattr(self, 'referenced_vars'):
            hash_values = ["#" + v for v in self.referenced_vars]
            at_values = ["@" + v for v in self.referenced_vars]
            print(f"更新补全数据: 添加{len(hash_values)}个#变量, {len(at_values)}个@变量")
            if hash_values:
                print(f"样例变量: {', '.join(sorted(hash_values)[:5])}")
        
        # 合并所有可能的值
        values.extend(hash_values)
        values.extend(at_values)
        
        # 确保值是唯一的并排序
        unique_values = sorted(set(values))
        
        # 更新补全器模型
        if isinstance(self.value_completer, CustomCompleter):
            self.value_completer.setModel(QStringListModel(unique_values))
        else:
            # 向后兼容处理
            model = QStringListModel(unique_values)
            self.value_completer.setModel(model)
    
    def get_attr_completer(self):
        """
        获取属性名补全器
        """
        return self.attr_completer
    
    def get_value_completer(self):
        """
        获取属性值补全器
        """
        return self.value_completer

class AttributeManagementDialog(QDialog):
    """
    自定义属性管理对话框
    """
    def __init__(self, parent=None, attribute_completer=None):
        super().__init__(parent)
        self.setWindowTitle("自定义属性名代码补全")
        self.resize(400, 300)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.attribute_completer = attribute_completer
        
        self.init_ui()
        self.load_attributes()
    
    def init_ui(self):
        """
        初始化UI
        """
        layout = QVBoxLayout(self)
        
        # 属性列表
        self.attr_list = QListWidget()
        self.attr_list.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.attr_list)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("添加属性")
        self.add_btn.clicked.connect(self.add_attribute)
        button_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("删除属性")
        self.remove_btn.clicked.connect(self.remove_attribute)
        button_layout.addWidget(self.remove_btn)
        
        layout.addLayout(button_layout)
        
        # 对话框按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_attributes(self):
        """
        加载自定义属性列表
        """
        if self.attribute_completer:
            self.attr_list.clear()
            for attr in self.attribute_completer.custom_attributes:
                self.attr_list.addItem(attr)
    
    def add_attribute(self):
        """
        添加自定义属性
        """
        attr, ok = QInputDialog.getText(self, "添加属性", "请输入属性名:")
        if ok and attr.strip():
            attr = attr.strip()
            if self.attribute_completer.add_custom_attribute(attr):
                self.attr_list.addItem(attr)
                QMessageBox.information(self, "成功", f"已添加属性 '{attr}'")
            else:
                QMessageBox.warning(self, "错误", f"属性 '{attr}' 已存在或无效")
    
    def remove_attribute(self):
        """
        删除自定义属性
        """
        selected_items = self.attr_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择一个属性")
            return
        
        attr = selected_items[0].text()
        result = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除属性 '{attr}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            if self.attribute_completer.remove_custom_attribute(attr):
                # 从列表中移除
                row = self.attr_list.row(selected_items[0])
                self.attr_list.takeItem(row)
                QMessageBox.information(self, "成功", f"已删除属性 '{attr}'")
            else:
                QMessageBox.warning(self, "错误", f"无法删除属性 '{attr}'")

class FileTabs:
    def __init__(self):
        self.file_comments = {}  # 作用注释: {file_path: {element_unique_id: comment}}
        # 旧版本兼容：注释路径映射缓存
        self.comment_path_map = {}
        # 路径到ID的映射，用于向后兼容旧版本的注释文件
        self.path_to_id_map = {}
    
    def load_file_comments(self, file_path):
        comment_file = file_path + ".comments"
        try:
            if os.path.exists(comment_file):
                with open(comment_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 检查是否是新格式（使用唯一ID的注释）
                    if isinstance(data, dict) and any(isinstance(k, str) and k.startswith("uuid:") for k in data.keys()):
                        # 新格式，直接使用
                        self.file_comments[file_path] = data
                    else:
                        # 旧格式，转换为新格式
                        self.file_comments[file_path] = {}
                        # 保存旧格式，以便后续转换
                        self.path_to_id_map[file_path] = data
            else:
                self.file_comments[file_path] = {}
            
            # 清空路径映射缓存
            self.comment_path_map = {}
        except Exception as e:
            print(f"加载文件注释失败: {e}")
            self.file_comments[file_path] = {}
    
    def save_file_comments(self, file_path):
        if file_path not in self.file_comments:
            return
            
        comment_file = file_path + ".comments"
        try:
            # 保存新格式的注释（基于唯一ID）
            with open(comment_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_comments[file_path], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存文件注释失败: {e}")
    
    def migrate_path_to_id(self, file_path, element_mapping):
        """将基于路径的注释迁移到基于ID的注释
        
        参数：
            file_path: 文件路径
            element_mapping: {path: element}映射
        """
        if file_path not in self.path_to_id_map or not self.path_to_id_map[file_path]:
            return
            
        # 确保file_comments[file_path]已初始化
        if file_path not in self.file_comments:
            self.file_comments[file_path] = {}
            
        # 遍历旧格式注释，转换为新格式
        for path, comment in self.path_to_id_map[file_path].items():
            if path in element_mapping:
                element = element_mapping[path]
                # 使用安全的方法获取元素ID
                unique_id = self._get_element_id(element)
                if unique_id:
                    # 使用"uuid:"前缀标记唯一ID，避免与路径混淆
                    self.file_comments[file_path]["uuid:" + unique_id] = comment
        
        # 清空旧格式缓存
        self.path_to_id_map[file_path] = {}
    
    def add_comment(self, file_path, element, comment):
        """添加或更新元素的作用注释
        
        参数：
            file_path: 文件路径
            element: 元素对象
            comment: 注释内容
        """
        if file_path not in self.file_comments:
            self.file_comments[file_path] = {}
        
        # 获取或创建元素的唯一ID
        unique_id = self._get_element_id(element)
        if unique_id:
            # 使用"uuid:"前缀标记
            self.file_comments[file_path]["uuid:" + unique_id] = comment
    
    def get_comment(self, file_path, element):
        """获取元素的作用注释
        
        参数：
            file_path: 文件路径
            element: 元素对象
        
        返回：
            注释内容，如不存在则返回空字符串
        """
        if file_path not in self.file_comments:
            return ""
        
        # 获取元素的唯一ID
        unique_id = self._get_element_id(element)
        if unique_id:
            key = "uuid:" + unique_id
            if key in self.file_comments[file_path]:
                return self.file_comments[file_path][key]
        
        return ""
    
    def _get_element_id(self, element):
        """安全地获取元素的唯一ID，如果不存在则创建
        
        参数：
            element: 元素对象
        
        返回：
            唯一ID字符串
        """
        try:
            if not hasattr(element, 'unique_id'):
                # 动态添加一个唯一ID属性
                import uuid
                setattr(element, 'unique_id', str(uuid.uuid4()))
            return element.unique_id
        except (AttributeError, TypeError):
            # 如果不能设置属性（例如lxml.etree._Element不允许），
            # 则使用元素的内存地址作为唯一标识
            return str(id(element))
    
    # 以下方法保留用于兼容旧版本
    def apply_path_mappings(self, file_path):
        """应用路径映射更新文件注释 - 旧版本兼容方法"""
        # 此方法在新系统中不再需要，仅保留用于兼容
        pass
    
    def add_path_mapping(self, old_path, new_path, force_exact=False):
        """添加路径映射记录 - 旧版本兼容方法"""
        # 此方法在新系统中不再需要，仅保留用于兼容
        pass
    
    def move_comment(self, file_path, old_path, new_path):
        """将注释从旧路径移动到新路径 - 旧版本兼容方法"""
        # 此方法在新系统中不再需要，仅保留用于兼容
        pass

class ImagePreviewDialog(QDialog):
    """图片预览对话框"""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片预览")
        self.setMinimumSize(400, 300)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # 图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        scroll_area.setWidget(self.image_label)
        
        # 加载图片
        self.pixmap = QPixmap(image_path)
        if not self.pixmap.isNull():
            self.image_label.setPixmap(self.pixmap)
            # 设置图片信息标签
            info_text = f"图片路径: {image_path}\n尺寸: {self.pixmap.width()}x{self.pixmap.height()} 像素"
            info_label = QLabel(info_text)
            layout.addWidget(info_label)
        else:
            self.image_label.setText(f"无法加载图片: {image_path}")
        
        layout.addWidget(scroll_area)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

class ColumnConfigDialog(QDialog):
    """自定义列配置对话框"""
    def __init__(self, parent=None, tree_columns=None):
        super().__init__(parent)
        self.tree_columns = tree_columns or {
            'default': ['元素', '功能注释', '作用注释', 'Name值'],
            'custom': [],
            'visible': {'功能注释': True, '作用注释': True, 'Name值': True}
        }
        self.setWindowTitle("结构树列配置")
        self.resize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 默认列区域标题
        default_label = QLabel("默认列显示设置")
        default_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(default_label)
        
        # 默认列显示设置
        default_columns_layout = QVBoxLayout()
        for col in self.tree_columns['default'][1:]:  # 跳过元素列
            checkbox = QCheckBox(col)
            checkbox.setChecked(self.tree_columns['visible'].get(col, True))
            checkbox.stateChanged.connect(lambda state, col=col: self.toggle_default_column(col, state))
            default_columns_layout.addWidget(checkbox)
        
        layout.addLayout(default_columns_layout)
        layout.addSpacing(10)
        
        # 自定义列区域标题
        custom_label = QLabel("自定义属性列")
        custom_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(custom_label)
        
        # 自定义列表
        self.custom_list = QListWidget()
        self.custom_list.setMinimumHeight(150)
        self.refresh_custom_list()
        layout.addWidget(self.custom_list)
        
        # 自定义列操作按钮
        buttons_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加列")
        add_btn.clicked.connect(self.add_custom_column)
        buttons_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("编辑列")
        edit_btn.clicked.connect(self.edit_custom_column)
        buttons_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("删除列")
        remove_btn.clicked.connect(self.remove_custom_column)
        buttons_layout.addWidget(remove_btn)
        
        layout.addLayout(buttons_layout)
        layout.addSpacing(10)
        
        # 对话框按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def refresh_custom_list(self):
        """刷新自定义列表显示"""
        self.custom_list.clear()
        for col in self.tree_columns['custom']:
            self.custom_list.addItem(col)
    
    def toggle_default_column(self, column, state):
        """切换默认列的可见性"""
        self.tree_columns['visible'][column] = (state == Qt.Checked)
    
    def add_custom_column(self):
        """添加自定义列"""
        column_name, ok = QInputDialog.getText(
            self, "添加自定义列", 
            "请输入要显示的元素属性名称:",
            QLineEdit.Normal
        )
        
        if ok and column_name:
            # 避免重复添加
            if column_name not in self.tree_columns['custom']:
                self.tree_columns['custom'].append(column_name)
                self.refresh_custom_list()
    
    def edit_custom_column(self):
        """编辑选中的自定义列"""
        current_item = self.custom_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择要编辑的列")
            return
        
        current_name = current_item.text()
        current_index = self.tree_columns['custom'].index(current_name)
        
        new_name, ok = QInputDialog.getText(
            self, "编辑自定义列", 
            "请输入新的属性名称:",
            QLineEdit.Normal,
            current_name
        )
        
        if ok and new_name and new_name != current_name:
            # 更新列名
            self.tree_columns['custom'][current_index] = new_name
            self.refresh_custom_list()
    
    def remove_custom_column(self):
        """删除选中的自定义列"""
        current_item = self.custom_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择要删除的列")
            return
        
        column_name = current_item.text()
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除列 '{column_name}' 吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.tree_columns['custom'].remove(column_name)
            self.refresh_custom_list()
    
    def get_config(self):
        """获取当前配置"""
        return self.tree_columns

class XMLEditorWindow(QMainWindow):
    """XML编辑器主窗口"""
    def __init__(self):
        super().__init__()
        
        # 初始化搜索相关的属性
        self.fuzzy_search = True  # 默认使用模糊搜索
        
        # 初始化其他成员变量
        self.current_file = None
        self.root = None
        self.tree_widget = None
        self.code_edit = None
        self.attr_table = None
        self.search_input = None
        self.search_type_combo = None
        self.case_sensitive_checkbox = None
        
        # 创建全局属性管理器
        self.global_attrs = GlobalAttributes()
        
        # 创建文件标签管理器
        self.file_tabs = FileTabs()
        
        # 当前打开的文件和当前选中的树节点
        self.current_file = None
        self.current_tree_item = None
        
        # 树项目和元素映射
        self.tree_items = {}  # 存储 element 到 TreeItem 的映射
        self.path_elements = {}  # 存储 element path 到 element 的映射
        
        # 撤销栈
        self.undo_stack = []
        self.max_undo_steps = 20  # 最大撤销步数
        
        # 创建属性自动补全管理器
        self.attr_completer = AttributeCompleter()
        
        # 自动补全功能启用状态
        self.autocomplete_enabled = True
        
        # 剪切板数据
        self.clipboard_elements = []
        
        # 初始化剪切操作
        self.cut_mode = False
        
        # 文件监视器
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self.on_file_changed)
        self.last_modified_time = 0
        
        # 树和属性表的列宽
        self.column_widths = {
            'tree': [200, 150, 150],  # 标签列、功能注释列、使用说明列的宽度
            'attr': [150, 200, 200]   # 属性名列、属性值列、注释列的宽度
        }
        
        # 加载列宽设置
        self.load_column_widths()
        
        # 加载自定义列配置
        self.tree_columns = {
            'default': ['标签', '功能注释', '使用说明'],
            'custom': [],
            'visible': {  # 列可见性设置
                '功能注释': True,
                '使用说明': True
            }
        }
        self.load_tree_columns()
        
        # 保存展开状态用的数据结构
        self.expanded_paths = {}
        
        # 初始化UI
        self.initUI()
    
    def initUI(self):
        """初始化UI界面"""
        # 设置窗口属性
        self.setWindowTitle('XML编辑器')
        self.resize(1200, 800)
        
        # 创建菜单栏
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        # 打开文件动作
        open_action = QAction('打开', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.openFile)
        file_menu.addAction(open_action)
        
        # 保存文件动作
        save_action = QAction('保存', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.silent_save)
        file_menu.addAction(save_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')
        
        # 撤销动作
        undo_action = QAction('撤销', self)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.triggered.connect(self.undo_last_action)
        edit_menu.addAction(undo_action)
        
        # 创建工具栏
        self.toolbar = QToolBar("主工具栏")
        self.addToolBar(self.toolbar)
        
        # 添加文件操作按钮到工具栏
        self.toolbar.addAction(open_action)
        self.toolbar.addAction(save_action)
        
        # 添加搜索区域
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        # 全局搜索框
        self.text_search_input = QLineEdit()
        self.text_search_input.setPlaceholderText("输入文本搜索内容...")
        self.text_search_input.setFixedWidth(200)
        self.text_search_input.textChanged.connect(self.on_text_search_changed)
        search_layout.addWidget(QLabel("全局搜索:"))
        search_layout.addWidget(self.text_search_input)
        
        # 添加模糊搜索和全字匹配按钮
        self.fuzzy_search_btn = QPushButton("模糊搜索")
        self.fuzzy_search_btn.setCheckable(True)
        self.fuzzy_search_btn.setChecked(True)
        self.fuzzy_search_btn.clicked.connect(self.toggle_search_mode)
        search_layout.addWidget(self.fuzzy_search_btn)
        
        self.exact_search_btn = QPushButton("全字匹配")
        self.exact_search_btn.setCheckable(True)
        self.exact_search_btn.clicked.connect(self.toggle_search_mode)
        search_layout.addWidget(self.exact_search_btn)
        
        # 清除全局搜索按钮
        clear_text_search_btn = QPushButton("清除")
        clear_text_search_btn.clicked.connect(self.clear_text_search)
        search_layout.addWidget(clear_text_search_btn)
        
        search_layout.addSpacing(20)  # 添加间距
        
        # 属性搜索框（原有的）
        self.attr_name_input = QLineEdit()
        self.attr_name_input.setPlaceholderText("输入属性名...")
        self.attr_name_input.setFixedWidth(150)
        self.attr_name_input.textChanged.connect(self.search_by_attribute)
        search_layout.addWidget(QLabel("属性搜索:"))
        search_layout.addWidget(self.attr_name_input)
        
        # 属性值搜索框（原有的）
        self.attr_value_input = QLineEdit()
        self.attr_value_input.setPlaceholderText("输入属性值...")
        self.attr_value_input.setFixedWidth(150)
        self.attr_value_input.textChanged.connect(self.search_by_attribute)
        search_layout.addWidget(QLabel("属性值:"))
        search_layout.addWidget(self.attr_value_input)
        
        # 清除属性搜索按钮（原有的）
        clear_attr_search_btn = QPushButton("清除")
        clear_attr_search_btn.clicked.connect(self.clear_attribute_search)
        search_layout.addWidget(clear_attr_search_btn)
        
        search_layout.addStretch()
        self.toolbar.addWidget(search_widget)
        
        # 添加属性搜索区域
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel("属性搜索: "))
        
        self.attr_name_input = QLineEdit()
        self.attr_name_input.setPlaceholderText("属性名")
        self.attr_name_input.setMaximumWidth(150)
        self.attr_name_input.returnPressed.connect(self.search_by_attribute)
        self.toolbar.addWidget(self.attr_name_input)
        
        self.attr_value_input = QLineEdit()
        self.attr_value_input.setPlaceholderText("属性值")
        self.attr_value_input.setMaximumWidth(150)
        self.attr_value_input.returnPressed.connect(self.search_by_attribute)
        self.toolbar.addWidget(self.attr_value_input)
        
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_by_attribute)
        self.toolbar.addWidget(self.search_button)
        
        # 添加清除搜索按钮
        self.clear_search_button = QPushButton("清除")
        self.clear_search_button.clicked.connect(self.clear_attribute_search)
        self.toolbar.addWidget(self.clear_search_button)
        
        # 创建菜单栏
        menubar = self.menuBar()
        
        # 添加文件菜单
        file_menu = menubar.addMenu('文件')
        
        open_action = QAction('打开', self)
        open_action.triggered.connect(self.openFile)
        file_menu.addAction(open_action)
        
        save_action = QAction('保存', self)
        save_action.triggered.connect(self.saveFile)
        file_menu.addAction(save_action)
        
        # 添加视图菜单
        view_menu = menubar.addMenu('视图')
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建主分割器（水平方向）
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 创建代码片段库
        self.snippet_library = XMLSnippetLibrary()
        self.snippet_library.set_main_window(self)
        
        # 创建编辑区域容器
        edit_area = QWidget()
        edit_layout = QHBoxLayout(edit_area)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧结构树区域
        tree_widget = QWidget()
        tree_layout = QVBoxLayout(tree_widget)
        
        tree_label = QLabel("结构树视图")
        tree_layout.addWidget(tree_label)
        
        # 添加按钮区域
        buttons_layout = QHBoxLayout()
        
        # 新建组按钮
        new_group_btn = QPushButton("新建组")
        new_group_btn.clicked.connect(self.add_new_group)
        buttons_layout.addWidget(new_group_btn)
        
        # 新建元素按钮
        new_element_btn = QPushButton("新建元素")
        new_element_btn.clicked.connect(self.add_new_element)
        buttons_layout.addWidget(new_element_btn)
        
        tree_layout.addLayout(buttons_layout)
        
        # 使用自定义树控件
        self.tree_widget = XMLTreeWidget()
        self.tree_widget.set_main_window(self)
        
        # 使用自定义列配置设置树视图的列
        visible_columns = self.get_visible_columns()
        self.tree_widget.setColumnCount(len(visible_columns))
        self.tree_widget.setHeaderLabels(visible_columns)
        
        # 设置列宽调整模式，允许用户手动调整
        self.tree_widget.header().setSectionResizeMode(QHeaderView.Interactive)
        
        # 应用保存的列宽
        for i, width in enumerate(self.column_widths['tree']):
            if i < self.tree_widget.header().count():
                self.tree_widget.header().resizeSection(i, width)
        
        # 允许最后一个列自动拉伸
        self.tree_widget.header().setStretchLastSection(True)
        self.tree_widget.itemClicked.connect(self.on_tree_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_tree_context_menu)
        tree_layout.addWidget(self.tree_widget)
        
        # 添加注释显示开关
        self.show_comments_action = QAction('显示XML注释', self)
        self.show_comments_action.setCheckable(True)
        self.show_comments_action.setChecked(self.tree_widget.show_comments)
        self.show_comments_action.triggered.connect(self.toggle_comments)
        view_menu.addAction(self.show_comments_action)
        
        # 添加列配置菜单项
        columns_action = QAction('配置结构树列...', self)
        columns_action.triggered.connect(self.configure_tree_columns)
        view_menu.addAction(columns_action)
        
        # 添加工具菜单
        tools_menu = menubar.addMenu('工具')
        
        # 自动补全开关
        self.autocomplete_action = QAction('启用属性自动补全', self)
        self.autocomplete_action.setCheckable(True)
        self.autocomplete_action.setChecked(self.autocomplete_enabled)
        self.autocomplete_action.triggered.connect(self.toggle_autocomplete)
        tools_menu.addAction(self.autocomplete_action)
        
        # 管理自定义属性
        manage_attrs_action = QAction('管理自定义属性...', self)
        manage_attrs_action.triggered.connect(self.manage_custom_attributes)
        tools_menu.addAction(manage_attrs_action)
        
        # 中间区域 - 属性表
        attr_widget = QWidget()
        attr_layout = QVBoxLayout(attr_widget)
        
        attr_label = QLabel("属性视图")
        attr_layout.addWidget(attr_label)
        
        self.attr_table = QTableWidget()
        self.attr_table.setColumnCount(4)  # 增加一列用于删除按钮
        self.attr_table.setHorizontalHeaderLabels(['属性', '值', '注释', ''])
        # 设置属性表列宽调整模式
        self.attr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # 应用保存的列宽设置
        for i, width in enumerate(self.column_widths['attr']):
            if i < self.attr_table.horizontalHeader().count():
                self.attr_table.horizontalHeader().resizeSection(i, width)
        # 删除按钮列固定宽度
        self.attr_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.attr_table.setColumnWidth(3, 30)  # 设置删除按钮列的宽度
        # 允许最后一列自动拉伸
        self.attr_table.horizontalHeader().setStretchLastSection(False)
        self.attr_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.attr_table.customContextMenuRequested.connect(self.show_attr_context_menu)
        self.attr_table.cellChanged.connect(self.on_attr_changed)
        
        # 设置属性表的自动补全
        self.setup_attr_table_completer()
        
        # 连接单元格激活信号，用于更新属性值补全器
        self.attr_table.cellDoubleClicked.connect(self.on_attr_table_cell_activated)
        
        attr_layout.addWidget(self.attr_table)
        
        # 添加图片预览区域（仅在点击Image元素时显示）
        self.image_preview = QLabel("选择Image元素以预览图片")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(150)
        self.image_preview.setMaximumHeight(200)
        self.image_preview.setStyleSheet("border: 1px solid #CCCCCC; background-color: #F8F8F8;")
        self.image_preview.setVisible(False)  # 初始隐藏
        attr_layout.addWidget(self.image_preview)
        
        # 右侧区域 - 源代码视图
        code_widget = QWidget()
        code_layout = QVBoxLayout(code_widget)
        
        code_label = QLabel("源代码视图")
        code_layout.addWidget(code_label)
        
        # 创建代码编辑器
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(False)  # 允许编辑
        
        # 设置代码编辑器的样式，确保在非焦点状态下也显示高亮
        self.code_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
            }
            QTextEdit:!focus {
                selection-background-color: yellow;
                selection-color: black;
            }
        """)
        
        # 代码更改后使用变更标志
        self.code_has_changes = False
        # 连接文本变更信号
        self.code_edit.textChanged.connect(self.on_code_text_changed)
        
        # 创建XML语法高亮器
        self.highlighter = XMLHighlighter(self.code_edit.document())
        
        code_layout.addWidget(self.code_edit)
        
        # 添加保存代码按钮
        self.save_code_btn = QPushButton("应用代码更改")
        self.save_code_btn.clicked.connect(self.apply_code_changes)
        self.save_code_btn.setEnabled(False)  # 初始禁用
        code_layout.addWidget(self.save_code_btn)
        
        # 添加到分割器
        splitter.addWidget(tree_widget)
        splitter.addWidget(attr_widget)
        splitter.addWidget(code_widget)
        
        # 设置初始分割大小
        splitter.setSizes([300, 400, 580])
        
        # 将分割器添加到编辑区域布局
        edit_layout.addWidget(splitter)
        
        # 将代码片段库和编辑区域添加到主分割器（先片段库，后编辑区）
        main_splitter.addWidget(self.snippet_library)
        main_splitter.addWidget(edit_area)
        
        # 设置初始分割大小
        main_splitter.setSizes([200, 1080])
        
        # 添加主分割器到主布局
        main_layout.addWidget(main_splitter)
        
        self.statusBar().showMessage('准备就绪')
        
        # 应用保存的列宽设置已在各视图初始化时完成，不需要重复
        
        self.show()
        
        # 保存主分割器和次级分割器的引用，以便后续操作
        self.main_splitter = main_splitter
        self.side_splitter = splitter
        
        # 加载布局设置，调整窗口和视图大小（延迟执行，确保UI已完全加载）
        QTimer.singleShot(100, self.load_layout_settings)
    
    def silent_save(self):
        """静默保存文件，无弹窗提示"""
        if not self.current_file:
            return
            
        try:
            # 如果代码视图有更改，先应用更改
            if self.code_has_changes:
                self.apply_code_changes()
            
            # 获取当前代码视图中的内容
            xml_content = self.code_edit.toPlainText()
            
            # 直接写入到文件，保留所有格式
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # 保存注释和其他设置
            self.global_attrs.save_comments()
            self.file_tabs.save_file_comments(self.current_file)
            self.save_column_widths()
            
            # 更新状态栏，显示短暂的保存成功消息
            self.statusBar().showMessage('已保存', 1000)
            
        except Exception as e:
            # 发生错误时在状态栏显示错误信息
            self.statusBar().showMessage(f'保存失败: {str(e)}', 3000)
            print(f"保存文件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def saveFile(self):
        """带确认对话框的保存文件方法"""
        if not self.current_file:
            file_path, _ = QFileDialog.getSaveFileName(self, '保存XML文件', '', 'XML文件 (*.xml);;所有文件 (*)')
            if not file_path:
                return
            self.current_file = file_path
            
        try:
            # 如果代码视图有更改，先应用更改
            if self.code_has_changes:
                result = QMessageBox.question(self, '保存确认', 
                                           '代码编辑器有未应用的更改，是否在保存前应用这些更改？',
                                           QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                
                if result == QMessageBox.Cancel:
                    return
                elif result == QMessageBox.Yes:
                    self.apply_code_changes()
            
            # 获取当前代码视图中的内容
            xml_content = self.code_edit.toPlainText()
            
            # 直接写入到文件，保留所有格式
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # 保存注释和其他设置
            self.global_attrs.save_comments()
            self.file_tabs.save_file_comments(self.current_file)
            self.save_column_widths()
            
            QMessageBox.information(self, '成功', '文件已保存')
            self.statusBar().showMessage(f'已保存到: {self.current_file}')
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存文件失败: {str(e)}')
            print(f"保存文件失败: {e}")
            import traceback
            traceback.print_exc()
    
    def formatXML(self, xml_str):
        """格式化XML字符串，但保留注释和原始空白行"""
        # 这个方法用于显示，不用于保存
        try:
            parser = etree.XMLParser(remove_blank_text=False)
            root = etree.fromstring(xml_str, parser)
            return etree.tostring(root, encoding='unicode', pretty_print=True)
        except:
            # 格式化失败时返回原始字符串
            return xml_str
    
    def update_tree_widget(self, save_expand_state=False):
        """更新树视图并迁移旧版本注释"""
        # 保存当前展开状态
        expand_states = {}
        if save_expand_state:
            expand_states = self.save_tree_expand_states()
            
        self.tree_widget.clear()
        self.tree_items = {}
        self.path_elements = {}
        
        if self.root is not None:
            root_item = self.add_element_to_tree(self.root, None)
            
            # 不再自动展开所有节点
            # self.tree_widget.expandAll()
            
            # 收起所有组，展开顶层
            if root_item:
                root_item.setExpanded(True)  # 展开根节点
                self.collapse_all_groups(root_item)
            
            # 迁移旧版本的基于路径的注释到基于ID的注释
            self.file_tabs.migrate_path_to_id(self.current_file, self.path_elements)
            
            # 恢复之前的展开状态
            if save_expand_state and expand_states:
                self.restore_tree_expand_states(expand_states)
    
    def get_element_path(self, element):
        """获取元素的XPath路径"""
        return self.tree.getpath(element)
    
    def add_element_to_tree(self, element, parent_item):
        base_dir = os.path.dirname(self.current_file) if self.current_file else None
        
        # 处理注释节点
        if isinstance(element, etree._Comment):
            if not self.tree_widget.show_comments:
                return None
            
            if parent_item is None:
                item = DraggableTreeItem(self.tree_widget, element, base_dir)
            else:
                item = DraggableTreeItem(parent_item, element, base_dir)
            
            # 设置注释文本（去掉<!-- -->标记）
            comment_text = element.text.strip()
            item.setText(0, comment_text)
            item.setForeground(0, self.tree_widget.comment_color)
            
            # 存储映射关系
            self.tree_items[element] = item
            path = self.get_element_path(element)
            self.path_elements[path] = element
            
            return item
        
        # 处理普通元素节点
        if parent_item is None:
            item = DraggableTreeItem(self.tree_widget, element, base_dir)
        else:
            item = DraggableTreeItem(parent_item, element, base_dir)
        
        # 存储映射关系
        self.tree_items[element] = item
        path = self.get_element_path(element)
        self.path_elements[path] = element
        
        # 获取可见列
        visible_columns = self.get_visible_columns()
        
        # 设置功能注释和作用注释（可见性取决于配置）
        if '功能注释' in visible_columns:
            col_position = visible_columns.index('功能注释')
            tag = element.tag
            if tag in self.global_attrs.feature_comments:
                item.setText(col_position, self.global_attrs.feature_comments[tag])
        
        if '作用注释' in visible_columns:
            col_position = visible_columns.index('作用注释')
            comment = self.file_tabs.get_comment(self.current_file, element)
            if comment:
                item.setText(col_position, comment)
        
        # 设置Name值（如果可见）
        if 'Name值' in visible_columns:
            col_position = visible_columns.index('Name值')
            if "name" in element.attrib:
                item.setText(col_position, element.attrib["name"])
        
        # 设置所有自定义列的值
        for attr_name in self.tree_columns['custom']:
            if attr_name in visible_columns:
                col_position = visible_columns.index(attr_name)
                
                # 处理可能以"值"结尾的自定义列
                real_attr_name = attr_name
                if attr_name.endswith("值"):
                    real_attr_name = attr_name[:-1]
                
                # 特殊处理Name值，确保使用小写的name
                if real_attr_name.lower() == "name":
                    real_attr_name = "name"
                
                if real_attr_name in element.attrib:
                    item.setText(col_position, element.attrib[real_attr_name])
        
        # 递归添加子元素和注释
        for child in element:
            if isinstance(child.tag, str) or isinstance(child, etree._Comment):  # 处理元素节点和注释节点
                self.add_element_to_tree(child, item)
        
        return item
    
    def update_code_view(self):
        if self.tree is not None:
            try:
                # 使用参数配置保持原始格式，包括自闭合标签
                xml_str = etree.tostring(self.tree, 
                                       encoding='utf-8', 
                                       xml_declaration=True,
                                       pretty_print=True,
                                       with_tail=True,
                                       method='xml',
                                       ).decode('utf-8')
                
                # 设置到代码视图
                self.code_edit.setText(xml_str)
                
            except Exception as e:
                print(f"更新代码视图失败: {e}")
                import traceback
                traceback.print_exc()
    
    def on_tree_item_clicked(self, item):
        self.current_tree_item = item
        element = item.element
        
        # 更新属性表
        self.update_attr_table(element)
        
        # 在代码视图中高亮显示对应元素
        self.highlight_element_in_code(element)
    
    def update_attr_table(self, element):
        self.attr_table.blockSignals(True)  # 阻止信号避免递归调用
        
        self.attr_table.setRowCount(0)
        
        # 根据元素类型决定是否显示图片预览
        if element.tag == "Image" and "src" in element.attrib and self.current_file:
            # 显示图片预览
            base_dir = os.path.dirname(self.current_file)
            src_value = element.attrib["src"]
            # 规范化路径
            src_value = src_value.replace('\\', '/').replace('//', '/')
            img_path = os.path.normpath(os.path.join(base_dir, src_value))
            
            # 加载并显示图片
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                # 保持比例缩放
                scaled_pixmap = pixmap.scaled(300, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_preview.setPixmap(scaled_pixmap)
                self.image_preview.setToolTip(f"图片路径: {img_path}\n尺寸: {pixmap.width()}x{pixmap.height()}")
                self.image_preview.setVisible(True)
            else:
                self.image_preview.setText(f"无法加载图片: {img_path}")
                self.image_preview.setVisible(True)
        else:
            # 隐藏图片预览
            self.image_preview.setVisible(False)
        
        for i, (attr, value) in enumerate(element.attrib.items()):
            self.attr_table.insertRow(i)
            
            # 属性名
            attr_item = QTableWidgetItem(attr)
            self.attr_table.setItem(i, 0, attr_item)
            
            # 属性值
            value_item = QTableWidgetItem(value)
            self.attr_table.setItem(i, 1, value_item)
            
            # 属性注释
            comment = ""
            if attr in self.global_attrs.attribute_comments:
                comment = self.global_attrs.attribute_comments[attr]
            comment_item = QTableWidgetItem(comment)
            self.attr_table.setItem(i, 2, comment_item)
            
            # 添加删除按钮
            delete_btn = QPushButton("X")
            delete_btn.clicked.connect(lambda _, row=i: self.delete_attribute(row))
            self.attr_table.setCellWidget(i, 3, delete_btn)
        
        # 添加一个空行用于添加新属性
        row = self.attr_table.rowCount()
        self.attr_table.insertRow(row)
        new_attr = QTableWidgetItem("<添加新属性>")
        new_attr.setForeground(QColor(128, 128, 128))
        self.attr_table.setItem(row, 0, new_attr)
        
        self.attr_table.blockSignals(False)
    
    def on_attr_changed(self, row, col):
        if not self.current_tree_item:
            return
        
        element = self.current_tree_item.element
        
        # 检查是否是最后一行（添加新属性）
        if row == self.attr_table.rowCount() - 1:
            attr_item = self.attr_table.item(row, 0)
            if attr_item and attr_item.text() != "<添加新属性>":
                # 用户在最后一行输入了新属性
                attr_name = attr_item.text().strip()
                
                # 检查属性名是否为空
                if not attr_name:
                    QMessageBox.warning(self, "错误", "属性名不能为空")
                    # 恢复默认文本
                    attr_item.setText("<添加新属性>")
                    return
                
                attr_value = ""
                value_item = self.attr_table.item(row, 1)
                if value_item:
                    attr_value = value_item.text()
                
                # 添加新属性
                element.set(attr_name, attr_value)
                
                # 更新注释
                comment_item = self.attr_table.item(row, 2)
                if comment_item and comment_item.text():
                    self.global_attrs.attribute_comments[attr_name] = comment_item.text()
                
                # 刷新UI
                self.update_attr_table(element)
                self.update_code_view()
                # 刷新树结构列显示
                self.refresh_tree_columns()
                return
        
        # 处理现有属性的更改
        if col < 2 and row < self.attr_table.rowCount() - 1:
            attr_item = self.attr_table.item(row, 0)
            value_item = self.attr_table.item(row, 1)
            
            if attr_item and value_item:
                attr_name = attr_item.text().strip()
                attr_value = value_item.text()
                
                # 检查属性名是否为空
                if not attr_name:
                    QMessageBox.warning(self, "错误", "属性名不能为空")
                    # 恢复原属性名
                    old_attrs = list(element.attrib.keys())
                    if row < len(old_attrs):
                        attr_item.setText(old_attrs[row])
                    return
                
                # 获取所有属性及其顺序
                old_attrs = list(element.attrib.keys())
                
                if row < len(old_attrs):
                    old_attr = old_attrs[row]
                    
                    # 如果只是修改属性值，并且属性名没变
                    if old_attr == attr_name:
                        # 直接设置新值，保持顺序不变
                        element.set(attr_name, attr_value)
                    else:
                        # 属性名也变了，需要重建所有属性来保持顺序
                        
                        # 保存所有属性值
                        attr_values = {}
                        for attr in old_attrs:
                            attr_values[attr] = element.attrib[attr]
                        
                        # 更新修改的属性
                        attr_values.pop(old_attr, None)  # 删除旧属性
                        attr_values[attr_name] = attr_value  # 添加新属性
                        
                        # 创建新的有序属性列表
                        new_attrs = []
                        for i, attr in enumerate(old_attrs):
                            if i == row:
                                new_attrs.append(attr_name)  # 在原位置插入新属性名
                            elif attr != old_attr:
                                new_attrs.append(attr)  # 保留其他属性
                        
                        # 清空所有属性
                        for attr in list(element.attrib.keys()):
                            del element.attrib[attr]
                        
                        # 按新顺序重新添加所有属性
                        for attr in new_attrs:
                            element.set(attr, attr_values[attr])
                    
                    # 将新属性名添加到自定义属性列表
                    if self.autocomplete_enabled:
                        self.attr_completer.add_custom_attribute(attr_name)
                    
                    # 更新属性值自动补全数据
                    if self.autocomplete_enabled:
                        # 更新自动补全数据
                        self.update_completers_from_xml()
                    
                    # 更新UI
                    self.update_attr_table(element)
                    self.update_code_view()
                    # 刷新树结构列显示
                    self.refresh_tree_columns()
        
        # 处理注释的更改
        if col == 2 and row < self.attr_table.rowCount() - 1:
            attr_item = self.attr_table.item(row, 0)
            comment_item = self.attr_table.item(row, 2)
            
            if attr_item and comment_item:
                attr_name = attr_item.text()
                comment = comment_item.text()
                
                # 更新属性注释
                self.global_attrs.attribute_comments[attr_name] = comment
    
    def delete_attribute(self, row):
        if not self.current_tree_item:
            return
        
        element = self.current_tree_item.element
        attr_item = self.attr_table.item(row, 0)
        
        if attr_item:
            attr_name = attr_item.text()
            
            # 检查属性是否存在
            if attr_name in element.attrib:
                # 获取所有属性及其顺序
                old_attrs = list(element.attrib.keys())
                
                # 保存所有属性值
                attr_values = {}
                for attr in old_attrs:
                    if attr != attr_name:  # 排除要删除的属性
                        attr_values[attr] = element.attrib[attr]
                
                # 清空所有属性
                for attr in list(element.attrib.keys()):
                    del element.attrib[attr]
                
                # 按原顺序重新添加所有属性（除了被删除的）
                for attr in old_attrs:
                    if attr != attr_name:
                        element.set(attr, attr_values[attr])
            
            # 更新UI
            self.update_attr_table(element)
            self.update_code_view()
            # 刷新树结构列显示
            self.refresh_tree_columns()
    
    def highlight_element_in_code(self, element):
        """在代码视图中高亮显示选中的元素或注释
        
        Args:
            element: 要高亮显示的XML元素或注释节点
        """
        if element is None:
            return
            
        try:
            # 获取元素的完整文本表示
            if isinstance(element, etree._Comment):
                # 对于注释节点，使用完整的注释文本
                search_text = f"<!--{element.text}-->"
            else:
                # 对于普通元素，获取其完整的开始标签文本
                search_text = etree.tostring(element, encoding='utf-8', with_tail=False).decode('utf-8')
                # 只保留开始标签部分
                end_pos = search_text.find('>')
                if end_pos != -1:
                    search_text = search_text[:end_pos + 1]
            
            # 在代码中查找并高亮
            self._find_and_highlight_text(search_text)
            
        except Exception as e:
            print(f"高亮显示失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_and_highlight_text(self, search_text):
        """在代码中查找并高亮指定的文本
        
        Args:
            search_text: 要查找和高亮的文本
        """
        if not self.code_edit or not search_text:
            return
            
        try:
            # 获取当前文档的全部文本
            document = self.code_edit.document()
            
            # 清除所有已有的高亮
            self.clear_search_highlighting()
            
            # 存储所有高亮选择
            extra_selections = []
            
            # 从文档开始处开始查找
            cursor = QTextCursor(document)
            
            # 在整个文档中查找匹配的文本
            first_match = None
            while True:
                cursor = document.find(search_text, cursor)
                if cursor.isNull():
                    break
                
                # 创建高亮选择
                selection = QTextEdit.ExtraSelection()
                
                # 设置高亮格式
                format = QTextCharFormat()
                format.setBackground(QColor(255, 255, 0))  # 黄色背景
                format.setForeground(QColor(0, 0, 0))      # 黑色文字
                selection.format = format
                
                # 设置选择范围
                selection.cursor = QTextCursor(cursor)
                extra_selections.append(selection)
                
                # 记录第一个匹配位置
                if first_match is None:
                    first_match = QTextCursor(cursor)
            
            # 应用所有高亮
            if extra_selections:
                # 保存当前的垂直滚动条位置
                vbar = self.code_edit.verticalScrollBar()
                current_scroll = vbar.value() if vbar else 0
                
                # 应用高亮
                self.code_edit.setExtraSelections(extra_selections)
                
                # 如果找到了匹配项，滚动到第一个匹配处
                if first_match:
                    # 设置光标到匹配位置
                    self.code_edit.setTextCursor(first_match)
                    self.code_edit.ensureCursorVisible()
                    
                    # 恢复原来的滚动位置
                    if vbar:
                        vbar.setValue(current_scroll)
            
        except Exception as e:
            print(f"查找和高亮文本失败: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_search_highlighting(self):
        """清除所有搜索高亮"""
        if not self.code_edit:
            return
        
        # 清除所有高亮
        self.code_edit.setExtraSelections([])
        
        # 重置光标位置，但不改变滚动位置
        cursor = self.code_edit.textCursor()
        cursor.clearSelection()
        self.code_edit.setTextCursor(cursor)
    
    def show_tree_context_menu(self, position):
        """显示树节点的右键菜单"""
        menu = QMenu()
        item = self.tree_widget.itemAt(position)
        
        if item:
            # 剪切动作
            cut_action = QAction('剪切', self)
            cut_action.setShortcut('Ctrl+X')
            cut_action.triggered.connect(self.cut_elements)
            menu.addAction(cut_action)
            
            # 复制动作
            copy_action = QAction('复制', self)
            copy_action.setShortcut('Ctrl+C')
            copy_action.triggered.connect(self.copy_elements)
            menu.addAction(copy_action)
            
            # 粘贴动作
            paste_action = QAction('粘贴', self)
            paste_action.setShortcut('Ctrl+V')
            paste_action.triggered.connect(self.paste_elements)
            menu.addAction(paste_action)
            
            menu.addSeparator()
            
            # 添加编辑选项（重命名）
            rename_action = QAction("编辑元素名称", self)
            rename_action.triggered.connect(lambda: self.start_rename_element(item))
            menu.addAction(rename_action)
            
            menu.addSeparator()
            
            # 添加源代码注释
            add_comment_action = QAction("添加源代码注释", self)
            add_comment_action.triggered.connect(lambda: self.add_source_comment(item))
            menu.addAction(add_comment_action)
            
            menu.addSeparator()
            
            # 删除操作
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(self.delete_elements)
            menu.addAction(delete_action)
            
            menu.addSeparator()
            
            # 跳转到代码
            goto_action = QAction("跳转到代码", self)
            goto_action.triggered.connect(self.goto_element_in_code)
            menu.addAction(goto_action)
            
            # 添加注释
            menu.addSeparator()
            
            add_feature_comment = QAction("添加功能注释", self)
            add_feature_comment.triggered.connect(lambda: self.add_feature_comment(item))
            menu.addAction(add_feature_comment)
            
            add_usage_comment = QAction("添加作用注释", self)
            add_usage_comment.triggered.connect(lambda: self.add_usage_comment(item))
            menu.addAction(add_usage_comment)
        
        menu.exec_(self.tree_widget.viewport().mapToGlobal(position))

    def show_attr_context_menu(self, position):
        """显示属性表的右键菜单"""
        menu = QMenu()
        
        # 添加属性动作
        add_attr_action = QAction("添加属性", self)
        add_attr_action.triggered.connect(self.add_attribute)
        menu.addAction(add_attr_action)
        
        # 获取当前选中的单元格
        current_item = self.attr_table.itemAt(position)
        if current_item:
            row = self.attr_table.row(current_item)
            if row < self.attr_table.rowCount() - 1:  # 不是最后一行（添加属性行）
                menu.addSeparator()
                
                # 删除属性动作
                delete_attr_action = QAction("删除属性", self)
                delete_attr_action.triggered.connect(lambda: self.delete_attribute(row))
                menu.addAction(delete_attr_action)
        
        menu.exec_(self.attr_table.viewport().mapToGlobal(position))

    def add_source_comment(self, item):
        """在选中项上方添加源代码注释
        
        Args:
            item: 选中的树项目
        """
        if not item or not hasattr(item, 'element'):
            return
            
        # 获取当前元素
        element = item.element
        parent = element.getparent()
        
        if parent is None:
            QMessageBox.warning(self, '错误', '不能在根元素上方添加注释')
            return
            
        # 创建状态管理器并保存当前状态
        tree_state = TreeStateManager(self.tree_widget).save_state()
        
        # 获取注释文本
        comment_text, ok = QInputDialog.getText(self, "添加源代码注释", "请输入注释内容:")
        if ok and comment_text.strip():
            # 创建注释节点
            comment = etree.Comment(comment_text.strip())
            
            # 获取当前元素在父元素中的位置
            index = parent.index(element)
            
            # 在当前元素之前插入注释
            parent.insert(index, comment)
            
            # 确保注释后有换行
            comment.tail = "\n"
            
            # 更新UI
            self.update_tree_widget(save_expand_state=False)
            self.update_code_view()
            
            # 延迟恢复树状态
            QTimer.singleShot(100, lambda: tree_state.restore_state())
    
    def paste_elements(self):
        """粘贴XML元素"""
        if not self.clipboard_elements:
            return
            
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
            
        target_item = selected_items[0]
        if not hasattr(target_item, 'element'):
            return
            
        target_element = target_item.element
        parent_element = target_element.getparent()
        
        if parent_element is None:
            QMessageBox.warning(self, '警告', '不能在根元素同级粘贴元素')
            return
            
        try:
            # 在执行操作前保存当前状态
            self.save_undo_state()
            
            # 创建状态管理器并保存当前状态
            tree_state = TreeStateManager(self.tree_widget).save_state()
            
            # 获取目标元素在父元素中的位置
            target_index = parent_element.index(target_element)
            
            # 遍历剪贴板中的元素
            for i, content in enumerate(self.clipboard_elements):
                try:
                    if self.clipboard_types[i] == 'comment':
                        # 创建新的注释节点
                        new_node = etree.Comment(content)
                        # 确保注释后有换行符
                        new_node.tail = "\n"
                    else:
                        # 解析XML字符串，确保使用正确的解析器设置
                        parser = etree.XMLParser(remove_blank_text=False,
                                              remove_comments=False,
                                              remove_pis=False,
                                              strip_cdata=False)
                        
                        # 使用BytesIO来解析XML字符串
                        new_node = etree.fromstring(content.encode('utf-8'), parser)
                        
                        # 确保元素有正确的换行符
                        if new_node.tail is None:
                            new_node.tail = "\n"
                    
                    # 在目标元素后面插入新节点
                    parent_element.insert(target_index + 1, new_node)
                    target_index += 1  # 更新插入位置，确保多个元素按顺序插入
                    
                except Exception as e:
                    print(f"解析XML片段失败: {e}")
                    raise
            
            # 更新UI
            self.update_tree_widget(save_expand_state=False)
            self.update_code_view()
            
            # 使用延迟调用恢复状态
            QTimer.singleShot(100, lambda: tree_state.restore_state())
            
            # 如果是剪切模式，清空剪贴板
            if self.cut_mode:
                self.clipboard_elements = []
                self.clipboard_types = []
                self.cut_mode = False
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'粘贴XML失败: {str(e)}')
            print(f"粘贴XML失败: {e}")
            import traceback
            traceback.print_exc()

    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_X:  # Ctrl+X
                self.cut_elements()
            elif event.key() == Qt.Key_C:  # Ctrl+C
                self.copy_elements()
            elif event.key() == Qt.Key_V:  # Ctrl+V
                self.paste_elements()
            elif event.key() == Qt.Key_Z:  # Ctrl+Z
                self.undo_last_action()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def cut_elements(self):
        """剪切选中的XML元素"""
        # 先复制元素
        self.copy_elements()
        # 设置剪切模式标志
        self.cut_mode = True
        # 删除原始元素
        self.delete_elements()

    def copy_elements(self):
        """复制选中的XML元素"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
            
        self.clipboard_elements = []
        self.clipboard_types = []  # 记录每个复制元素的类型
        self.cut_mode = False
        
        for item in selected_items:
            if hasattr(item, 'element'):
                element = item.element
                if isinstance(element, etree._Comment):
                    # 对于注释节点，直接保存注释文本
                    self.clipboard_elements.append(element.text)
                    self.clipboard_types.append('comment')
                else:
                    # 对于普通元素，使用tostring方法
                    xml_str = etree.tostring(element, 
                                          encoding='utf-8',
                                          xml_declaration=False,
                                          pretty_print=True,
                                          with_tail=True).decode('utf-8')
                    self.clipboard_elements.append(xml_str)
                    self.clipboard_types.append('element')
    
    def delete_elements(self):
        """删除选中的XML元素，保持树视图状态"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        try:
            # 在执行操作前保存当前状态
            self.save_undo_state()
            
            # 创建状态管理器并保存当前状态
            tree_state = TreeStateManager(self.tree_widget).save_state()
            
            # 执行删除操作
            for item in selected_items:
                element = item.element
                parent = element.getparent()
                
                if parent is not None:
                    parent.remove(element)
            
            # 更新UI
            self.update_tree_widget(save_expand_state=False)
            self.update_code_view()
            
            # 使用延迟调用恢复状态，确保UI已完全更新
            QTimer.singleShot(100, lambda: tree_state.restore_state())
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'删除XML元素失败: {str(e)}')
            print(f"删除XML元素失败: {e}")
            import traceback
            traceback.print_exc()
    
    def goto_element_in_code(self):
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return
        
        # 高亮第一个选中元素
        element = selected_items[0].element
        self.highlight_element_in_code(element)
    
    def add_feature_comment(self, item):
        element = item.element
        tag = element.tag
        
        current_comment = ""
        if tag in self.global_attrs.feature_comments:
            current_comment = self.global_attrs.feature_comments[tag]
        
        comment, ok = QInputDialog.getText(self, "添加功能注释", 
                                         f"为 {tag} 元素添加功能注释:", 
                                         QLineEdit.Normal, 
                                         current_comment)
        
        if ok and comment:
            # 保存全局功能注释
            self.global_attrs.feature_comments[tag] = comment
            
            # 更新所有相同标签的树项
            for i in range(self.tree_widget.topLevelItemCount()):
                self.update_comment_recursive(self.tree_widget.topLevelItem(i), tag, comment, 1)
    
    def add_usage_comment(self, item):
        element = item.element
        
        # 获取当前注释
        current_comment = self.file_tabs.get_comment(self.current_file, element)
        
        comment, ok = QInputDialog.getText(self, "添加作用注释", 
                                         "添加作用注释:", 
                                         QLineEdit.Normal, 
                                         current_comment)
        
        if ok and comment:
            # 保存作用注释
            self.file_tabs.add_comment(self.current_file, element, comment)
            
            # 更新当前项
            item.setText(2, comment)
    
    def update_comment_recursive(self, item, tag, comment, col):
        if item.text(0) == tag:
            item.setText(col, comment)
        
        # 递归更新所有子项
        for i in range(item.childCount()):
            self.update_comment_recursive(item.child(i), tag, comment, col)
    
    def add_attribute(self):
        if not self.current_tree_item:
            return
        
        # 确保自动补全器已更新
        if self.autocomplete_enabled:
            self.update_completers_from_xml()
        
        # 更新属性表，最后一行已经是用于添加新属性的行
        self.attr_table.setCurrentCell(self.attr_table.rowCount() - 1, 0)
        self.attr_table.editItem(self.attr_table.currentItem())
    
    def on_code_text_changed(self):
        """当代码编辑器内容变更时调用"""
        self.code_has_changes = True
        self.save_code_btn.setEnabled(True)
    
    def apply_code_changes(self):
        """应用代码变更到XML树"""
        if not self.code_has_changes:
            return
            
        try:
            # 创建状态管理器并保存当前状态
            tree_state = TreeStateManager(self.tree_widget).save_state()
            
            # 获取编辑后的XML内容
            xml_content = self.code_edit.toPlainText()
            
            # 将XML内容转换为bytes
            xml_bytes = xml_content.encode('utf-8')
            
            # 创建解析器，保留所有格式
            parser = etree.XMLParser(remove_blank_text=False, 
                                   remove_comments=False,
                                   remove_pis=False,
                                   strip_cdata=False)
            
            # 使用BytesIO和parser解析XML
            updated_tree = etree.parse(io.BytesIO(xml_bytes), parser)
            
            # 更新树和根元素
            self.tree = updated_tree
            self.root = self.tree.getroot()
            
            # 更新树视图，不保存展开状态（因为我们已经保存了）
            self.update_tree_widget(save_expand_state=False)
            
            # 使用延迟调用恢复状态，确保UI已完全更新
            QTimer.singleShot(100, lambda: tree_state.restore_state())
            
            # 重置更改标志
            self.code_has_changes = False
            self.save_code_btn.setEnabled(False)
            
            # 显示成功消息
            self.statusBar().showMessage('代码更改已应用', 3000)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'应用代码更改失败: {str(e)}')
            print(f"应用代码更改失败: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_tree_comments(self):
        """刷新树节点的注释显示"""
        if not self.current_file:
            return
            
        # 获取可见列
        visible_columns = self.get_visible_columns()
        
        # 更新所有树节点的注释
        for element, item in self.tree_items.items():
            # 更新功能注释
            tag = element.tag
            if '功能注释' in visible_columns:
                col_position = visible_columns.index('功能注释')
                if tag in self.global_attrs.feature_comments:
                    item.setText(col_position, self.global_attrs.feature_comments[tag])
                else:
                    item.setText(col_position, "")
            
            # 更新作用注释
            if '作用注释' in visible_columns:
                col_position = visible_columns.index('作用注释')
                comment = self.file_tabs.get_comment(self.current_file, element)
                item.setText(col_position, comment if comment else "")
    
    def refresh_tree_columns(self):
        """强制刷新树视图的列显示和布局"""
        if not self.root:
            return
            
        # 获取当前可见列
        visible_columns = self.get_visible_columns()
        
        # 重置列设置
        self.tree_widget.setColumnCount(len(visible_columns))
        self.tree_widget.setHeaderLabels(visible_columns)
        
        # 刷新所有树节点的列值
        for element, item in self.tree_items.items():
            # 对每个元素重新设置所有列的值
            tag = element.tag
            
            # 设置功能注释（如果可见）
            if '功能注释' in visible_columns:
                col_position = visible_columns.index('功能注释')
                if tag in self.global_attrs.feature_comments:
                    item.setText(col_position, self.global_attrs.feature_comments[tag])
                else:
                    item.setText(col_position, "")
            
            # 设置作用注释（如果可见）
            if '作用注释' in visible_columns:
                col_position = visible_columns.index('作用注释')
                comment = self.file_tabs.get_comment(self.current_file, element)
                item.setText(col_position, comment if comment else "")
            
            # 设置Name值（如果可见）
            if 'Name值' in visible_columns:
                col_position = visible_columns.index('Name值')
                if "name" in element.attrib:
                    item.setText(col_position, element.attrib["name"])
                else:
                    item.setText(col_position, "")
            
            # 设置所有自定义列的值
            for attr_name in self.tree_columns['custom']:
                if attr_name in visible_columns:
                    col_position = visible_columns.index(attr_name)
                    
                    # 处理可能以"值"结尾的自定义列
                    real_attr_name = attr_name
                    if attr_name.endswith("值"):
                        real_attr_name = attr_name[:-1]
                    
                    # 特殊处理Name值，确保使用小写的name
                    if real_attr_name.lower() == "name":
                        real_attr_name = "name"
                    
                    if real_attr_name in element.attrib:
                        item.setText(col_position, element.attrib[real_attr_name])
                    else:
                        item.setText(col_position, "")
        
        # 应用保存的列宽
        for i, width in enumerate(self.column_widths['tree']):
            if i < self.tree_widget.header().count():
                self.tree_widget.header().resizeSection(i, width)
        
        # 刷新视图
        self.tree_widget.viewport().update()
    
    def save_tree_expand_states(self):
        """保存树节点的展开状态"""
        expand_states = {}
        
        # 为每个元素记录其展开状态
        for element, item in self.tree_items.items():
            if hasattr(element, 'unique_id'):
                try:
                    # 使用元素ID作为键
                    element_id = element.unique_id
                    expand_states[element_id] = item.isExpanded()
                except (AttributeError, TypeError):
                    # 使用元素对象的ID作为备选键
                    expand_states[f"id_{id(element)}"] = item.isExpanded()
            else:
                # 使用元素对象的ID作为备选键
                expand_states[f"id_{id(element)}"] = item.isExpanded()
        
        return expand_states
    
    def restore_tree_expand_states(self, expand_states):
        """恢复树节点的展开状态"""
        for element, item in self.tree_items.items():
            try:
                # 尝试使用元素ID查找展开状态
                if hasattr(element, 'unique_id'):
                    element_id = element.unique_id
                    if element_id in expand_states:
                        item.setExpanded(expand_states[element_id])
                        continue
                
                # 备选方案：使用元素对象的ID
                backup_id = f"id_{id(element)}"
                if backup_id in expand_states:
                    item.setExpanded(expand_states[backup_id])
            except Exception:
                # 忽略任何错误，保持默认状态
                pass
    
    def collapse_all_groups(self, parent_item):
        """递归收起所有Group元素"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            # 如果是Group元素，则收起
            if hasattr(child, 'element') and child.element.tag == "Group":
                child.setExpanded(False)
            # 递归处理子节点
            self.collapse_all_groups(child)
    
    def on_tree_item_double_clicked(self, item, column):
        """处理树视图项的双击事件
        
        Args:
            item: 被双击的QTreeWidgetItem
            column: 被双击的列索引
        """
        # 获取元素
        element = item.element
        if element is None:
            return
        
        # 如果是注释节点且是第一列
        if isinstance(element, etree._Comment) and column == 0:
            # 创建一个编辑器
            editor = CustomLineEdit(self.tree_widget)
            editor.setFrame(False)
            
            # 设置当前值（去掉<!-- -->标记）
            current_value = element.text.strip()
            editor.setText(current_value)
            
            # 获取项目的矩形区域
            rect = self.tree_widget.visualItemRect(item)
            rect.setLeft(self.tree_widget.columnViewportPosition(column))
            rect.setWidth(self.tree_widget.columnWidth(column))
            
            # 确保编辑器在正确的位置
            editor.setParent(self.tree_widget.viewport())
            editor.setGeometry(rect)
            editor.show()
            editor.setFocus()
            editor.selectAll()
            
            # 存储原始值和相关信息
            editor.original_value = current_value
            editor.item = item
            editor.column = column
            editor.element = element
            
            # 连接编辑完成信号
            def finish_editing():
                new_value = editor.text()
                if new_value != editor.original_value:
                    # 更新注释内容
                    element.text = new_value
                    item.setText(column, new_value)
                    
                    # 更新代码视图
                    self.update_code_view()
                    
                    # 标记为已修改
                    self.is_modified = True
                
                # 移除编辑器
                editor.deleteLater()
            
            editor.editingFinished.connect(finish_editing)
            return
        
        # 如果列索引为0（第一列是元素名称列），不进行编辑
        if column == 0:
            return
        
        # 获取列标题名称
        column_name = self.tree_widget.headerItem().text(column)
        
        # 创建一个编辑器
        editor = CustomLineEdit(self.tree_widget)
        editor.setFrame(False)
        
        # 根据列类型设置当前值和处理逻辑
        if column_name == "功能注释":
            # 功能注释，从全局属性管理器中获取
            tag = element.tag
            current_value = self.global_attrs.feature_comments.get(tag, "")
            editor.setText(current_value)
            is_attr_edit = False
        elif column_name == "使用说明" or column_name == "作用注释":
            # 作用注释，从文件标签管理器中获取
            if self.current_file:
                current_value = self.file_tabs.get_comment(self.current_file, element) or ""
                editor.setText(current_value)
            else:
                current_value = ""
                editor.setText(current_value)
            is_attr_edit = False
        else:
            # 其他列视为属性编辑
            # 处理"XXX值"类型的列名
            attr_name = column_name
            if attr_name.endswith("值"):
                attr_name = attr_name[:-1]  # 去掉"值"字
                
            # 特殊处理Name值，确保使用小写的name
            if attr_name.lower() == "name":
                attr_name = "name"
            
            # 设置当前值
            current_value = element.get(attr_name, "")
            editor.setText(current_value)
            is_attr_edit = True
        
        # 如果启用了自动完成，设置自动完成器（仅对属性编辑有效）
        if is_attr_edit and self.autocomplete_enabled and hasattr(self, 'attr_completer'):
            # 更新值自动完成列表
            self.attr_completer.update_value_completer(attr_name)
            # 获取值自动完成器
            value_completer = self.attr_completer.get_value_completer()
            # 设置编辑器的自动完成器
            editor.setCustomCompleter(value_completer)
        
        # 获取项目的矩形区域
        rect = self.tree_widget.visualItemRect(item)
        rect.setLeft(self.tree_widget.columnViewportPosition(column))
        rect.setWidth(self.tree_widget.columnWidth(column))
        
        # 确保编辑器在正确的位置
        editor.setParent(self.tree_widget.viewport())
        editor.setGeometry(rect)
        editor.show()
        editor.setFocus()
        editor.selectAll()  # 选中所有文本，方便用户直接编辑
        
        # 存储原始值和相关信息，用于后续处理
        editor.original_value = current_value
        editor.item = item
        editor.column = column
        editor.column_name = column_name
        editor.is_attr_edit = is_attr_edit
        if is_attr_edit and attr_name != column_name:
            editor.attr_name = attr_name
        else:
            editor.attr_name = column_name
        
        # 连接编辑完成信号
        def finish_editing():
            new_value = editor.text()
            if new_value != editor.original_value:
                if editor.is_attr_edit:
                    # 属性编辑：更新元素属性
                    if new_value:
                        element.set(editor.attr_name, new_value)
                    else:
                        # 如果值为空，删除该属性
                        if editor.attr_name in element.attrib:
                            del element.attrib[editor.attr_name]
                    
                    # 更新代码视图
                    self.update_code_view()
                elif editor.column_name == "功能注释":
                    # 功能注释：更新全局属性管理器
                    tag = element.tag
                    self.global_attrs.feature_comments[tag] = new_value
                    
                    # 保存功能注释
                    self.global_attrs.save_comments()
                elif editor.column_name in ["使用说明", "作用注释"]:
                    # 作用注释：更新文件标签管理器
                    if self.current_file:
                        self.file_tabs.add_comment(self.current_file, element, new_value)
                        
                        # 保存作用注释
                        self.file_tabs.save_file_comments(self.current_file)
                
                # 更新树项目显示
                item.setText(column, new_value)
                
                # 标记为已修改
                self.is_modified = True
            
            # 移除编辑器
            editor.deleteLater()
        
        # 添加处理Escape键的功能，用于取消编辑
        def handle_key_press(event):
            if event.key() == Qt.Key_Escape:
                # 取消编辑，恢复原值
                editor.setText(editor.original_value)
                editor.deleteLater()
                event.accept()
            else:
                # 其他键正常处理
                editor.keyPressEvent_original(event)
        
        # 保存原始的keyPressEvent方法
        editor.keyPressEvent_original = editor.keyPressEvent
        # 替换为自定义的方法
        editor.keyPressEvent = handle_key_press
        
        # 连接完成编辑的信号
        editor.editingFinished.connect(finish_editing)
        
        # 连接按下Enter键的事件
        editor.returnPressed.connect(finish_editing)
    
    # 添加新方法用于创建新组
    def add_new_group(self):
        if not self.current_file or not self.tree:
            QMessageBox.warning(self, '警告', '请先打开XML文件')
            return
        
        # 获取当前选中的项
        selected_items = self.tree_widget.selectedItems()
        parent_element = self.root
        insert_index = 0
        
        if selected_items:
            selected_item = selected_items[0]
            selected_element = selected_item.element
            
            # 确定插入位置：如果选中的是根元素，插入为其子元素，否则插入为同级元素
            if selected_element == self.root:
                parent_element = self.root
                insert_index = len(list(self.root))
            else:
                parent_element = selected_element.getparent()
                if parent_element is not None:
                    # 获取在父元素中的索引
                    for i, child in enumerate(parent_element):
                        if child == selected_element:
                            insert_index = i + 1
                            break
        
        # 创建新的Group元素
        new_group = etree.Element("Group")
        
        # 添加换行符
        new_group.tail = "\n"
        if insert_index == 0 and parent_element == self.root:
            # 如果是添加到开头，确保在元素前也有换行
            new_group.text = "\n"
        
        # 插入到指定位置
        if parent_element is not None:
            if insert_index >= len(list(parent_element)):
                parent_element.append(new_group)
            else:
                parent_element.insert(insert_index, new_group)
            
            # 更新UI
            self.update_tree_widget(save_expand_state=True)
            self.update_code_view()
            
            # 选中新创建的组
            for element, item in self.tree_items.items():
                if element == new_group:
                    self.tree_widget.setCurrentItem(item)
                    self.tree_widget.scrollToItem(item)
                    
                    # 允许用户直接编辑新组的名称
                    self.start_rename_element(item)
                    break
    
    # 添加新方法用于创建新元素
    def add_new_element(self):
        if not self.current_file or not self.tree:
            QMessageBox.warning(self, '警告', '请先打开XML文件')
            return
        
        # 获取用户输入的元素名称
        element_name, ok = QInputDialog.getText(self, '新建元素', '请输入元素名称:')
        if not ok or not element_name.strip():
            return
        
        # 规范化元素名称
        element_name = element_name.strip()
        
        # 验证元素名称是否合法
        try:
            # 先尝试创建一个临时元素验证名称合法性
            test_element = etree.Element(element_name)
        except ValueError as e:
            QMessageBox.warning(self, '错误', f'无效的元素名称: {e}')
            return
        
        # 获取当前选中的项
        selected_items = self.tree_widget.selectedItems()
        parent_element = self.root
        insert_index = 0
        
        if selected_items:
            selected_item = selected_items[0]
            selected_element = selected_item.element
            
            # 确定插入位置：如果选中的是根元素，插入为其子元素，否则插入为同级元素
            if selected_element == self.root:
                parent_element = self.root
                insert_index = len(list(self.root))
            else:
                parent_element = selected_element.getparent()
                if parent_element is not None:
                    # 获取在父元素中的索引
                    for i, child in enumerate(parent_element):
                        if child == selected_element:
                            insert_index = i + 1
                            break
        
        # 创建新元素
        new_element = etree.Element(element_name)
        
        # 添加换行符
        new_element.tail = "\n"
        if insert_index == 0 and parent_element == self.root:
            # 如果是添加到开头，确保在元素前也有换行
            new_element.text = "\n"
        
        # 插入到指定位置
        if parent_element is not None:
            if insert_index >= len(list(parent_element)):
                parent_element.append(new_element)
            else:
                parent_element.insert(insert_index, new_element)
            
            # 更新UI
            self.update_tree_widget(save_expand_state=True)
            self.update_code_view()
            
            # 选中新创建的元素
            for element, item in self.tree_items.items():
                if element == new_element:
                    self.tree_widget.setCurrentItem(item)
                    self.tree_widget.scrollToItem(item)
                    
                    # 直接显示属性表以便于添加属性
                    self.on_tree_item_clicked(item)
                    break
    
    def start_rename_element(self, item):
        """启动元素重命名操作"""
        if not item:
            return
            
        # 断开任何现有的重命名处理程序连接
        self.disconnect_rename_handler()
        
        # 使项目可编辑
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        
        # 开始编辑
        self.tree_widget.editItem(item, 0)
        
        # 连接编辑完成事件
        self.tree_widget.itemChanged.connect(self.on_tree_item_renamed)
    
    def on_tree_item_renamed(self, item, column):
        """处理树项目重命名事件"""
        if not item or column != 0:
            return
            
        # 获取新的标签名
        new_tag = item.text(0)
        
        # 验证新标签名是否合法
        try:
            # 先尝试创建一个临时元素验证名称合法性
            test_element = etree.Element(new_tag)
        except ValueError as e:
            QMessageBox.warning(self, '错误', f'无效的元素名称: {e}')
            # 还原标签名
            if hasattr(item, 'element'):
                item.setText(0, item.element.tag)
            # 断开信号连接
            self.disconnect_rename_handler()
            return
        
        # 检查元素是否存在
        if hasattr(item, 'element'):
            element = item.element
            old_tag = element.tag
            
            try:
                # 保存XML树的原始字符串表示，以便出错时恢复
                original_xml = etree.tostring(self.tree, pretty_print=True, encoding='utf-8').decode('utf-8')
                
                # 保存父元素和位置
                parent = element.getparent()
                if parent is None:
                    # 如果是根元素，不允许重命名
                    QMessageBox.warning(self, '错误', '不能重命名根元素')
                    item.setText(0, old_tag)
                    self.disconnect_rename_handler()
                    return
                
                index = parent.index(element)
                
                # 创建具有相同属性和子元素的新元素
                new_element = etree.Element(new_tag)
                
                # 复制所有属性
                for key, value in element.attrib.items():
                    new_element.set(key, value)
                
                # 保存子元素的引用
                children = list(element)
                
                # 复制所有子元素到新元素
                for child in children:
                    element.remove(child)
                    new_element.append(child)
                
                # 如果原元素有文本，也复制过来
                if element.text:
                    new_element.text = element.text
                
                # 如果原元素有尾部文本，也复制过来
                if element.tail:
                    new_element.tail = element.tail
                
                # 从父元素中移除原元素
                parent.remove(element)
                
                # 在相同位置插入新元素
                parent.insert(index, new_element)
                
                # 确保空元素使用<Tag></Tag>格式
                if len(new_element) == 0 and not new_element.text:
                    new_element.text = ""
                
                # 更新UI
                self.update_tree_widget(save_expand_state=True)
                self.update_code_view()
                
                # 选中重命名后的元素
                for e, i in self.tree_items.items():
                    if e == new_element:
                        self.tree_widget.setCurrentItem(i)
                        break
            
            except Exception as e:
                # 出错时恢复原始XML
                try:
                    parser = etree.XMLParser(remove_blank_text=False, 
                                          remove_comments=False,
                                          remove_pis=False,
                                          strip_cdata=False)
                    self.tree = etree.parse(io.StringIO(original_xml), parser)
                    self.root = self.tree.getroot()
                    self.update_tree_widget(save_expand_state=True)
                    self.update_code_view()
                except Exception as restore_err:
                    print(f"恢复原始XML失败: {restore_err}")
                
                QMessageBox.critical(self, '错误', f'重命名元素时出错: {str(e)}')
                item.setText(0, old_tag)
        
        # 断开信号连接，避免重复处理
        self.disconnect_rename_handler()
    
    def disconnect_rename_handler(self):
        """安全断开重命名处理程序的信号连接"""
        try:
            # 尝试断开信号连接
            self.tree_widget.itemChanged.disconnect(self.on_tree_item_renamed)
        except (TypeError, RuntimeError):
            # 忽略信号未连接或其他断开错误
            pass
    
    def load_column_widths(self):
        """从文件加载列宽设置"""
        try:
            if os.path.exists('column_widths.json'):
                with open('column_widths.json', 'r', encoding='utf-8') as f:
                    self.column_widths = json.load(f)
        except Exception as e:
            print(f"加载列宽设置失败: {e}")
    
    def save_column_widths(self):
        """保存列宽设置到文件"""
        try:
            # 更新当前列宽设置
            for i in range(self.tree_widget.header().count()):
                if i < len(self.column_widths['tree']):
                    self.column_widths['tree'][i] = self.tree_widget.header().sectionSize(i)
                else:
                    self.column_widths['tree'].append(self.tree_widget.header().sectionSize(i))
            
            for i in range(self.attr_table.horizontalHeader().count()):
                if i < len(self.column_widths['attr']):
                    self.column_widths['attr'][i] = self.attr_table.horizontalHeader().sectionSize(i)
                else:
                    self.column_widths['attr'].append(self.attr_table.horizontalHeader().sectionSize(i))
            
            # 保存到文件
            with open('column_widths.json', 'w', encoding='utf-8') as f:
                json.dump(self.column_widths, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存列宽设置失败: {e}")
    
    def save_layout_settings(self):
        """
        保存窗口布局设置，包括窗口大小、位置、分割器位置和列宽度
        """
        try:
            settings = {}
            
            # 保存窗口大小和位置
            settings['window_geometry'] = {
                'width': self.width(),
                'height': self.height(),
                'x': self.x(),
                'y': self.y()
            }
            
            # 保存分割器位置
            if hasattr(self, 'main_splitter'):
                settings['main_splitter_sizes'] = [size for size in self.main_splitter.sizes()]
            
            if hasattr(self, 'left_splitter'):
                settings['left_splitter_sizes'] = [size for size in self.left_splitter.sizes()]
                
            if hasattr(self, 'side_splitter'):
                settings['right_splitter_sizes'] = [size for size in self.side_splitter.sizes()]
                
            # 保存树视图列宽度
            if hasattr(self, 'tree_widget'):
                column_widths = []
                for i in range(self.tree_widget.columnCount()):
                    column_widths.append(self.tree_widget.columnWidth(i))
                settings['tree_column_widths'] = column_widths
            
            # 保存属性表列宽度
            if hasattr(self, 'attr_table'):
                attr_column_widths = []
                for i in range(self.attr_table.columnCount()):
                    attr_column_widths.append(self.attr_table.columnWidth(i))
                settings['attr_column_widths'] = attr_column_widths
            
            # 保存设置到JSON文件
            with open('layout_settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
            print("布局设置已保存")
        except Exception as e:
            print(f"保存布局设置时发生错误: {e}")
    
    def load_layout_settings(self):
        """
        加载窗口布局设置
        """
        try:
            if not os.path.exists('layout_settings.json'):
                print("没有找到布局设置文件，使用默认布局")
                return
                
            with open('layout_settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
            # 恢复窗口大小和位置
            if 'window_geometry' in settings:
                geo = settings['window_geometry']
                self.resize(geo['width'], geo['height'])
                self.move(geo['x'], geo['y'])
                
            # 恢复分割器位置
            if 'main_splitter_sizes' in settings and hasattr(self, 'main_splitter'):
                sizes = settings['main_splitter_sizes']
                self.main_splitter.setSizes(sizes)
                
            if 'left_splitter_sizes' in settings and hasattr(self, 'left_splitter'):
                sizes = settings['left_splitter_sizes']
                self.left_splitter.setSizes(sizes)
                
            if 'right_splitter_sizes' in settings and hasattr(self, 'side_splitter'):
                sizes = settings['right_splitter_sizes']
                self.side_splitter.setSizes(sizes)
                
            # 恢复树视图列宽度
            if 'tree_column_widths' in settings and hasattr(self, 'tree_widget'):
                widths = settings['tree_column_widths']
                for i, width in enumerate(widths):
                    if i < self.tree_widget.columnCount():
                        self.tree_widget.setColumnWidth(i, width)
                        
            # 恢复属性表列宽度
            if 'attr_column_widths' in settings and hasattr(self, 'attr_table'):
                widths = settings['attr_column_widths']
                for i, width in enumerate(widths):
                    if i < self.attr_table.columnCount():
                        self.attr_table.setColumnWidth(i, width)
                        
            print("布局设置已加载")
        except Exception as e:
            print(f"加载布局设置时发生错误: {e}")
    
    def closeEvent(self, event):
        """
        窗口关闭事件，保存布局设置
        """
        try:
            self.save_layout_settings()
            
            # 执行原有的关闭操作
            super(XMLEditorWindow, self).closeEvent(event)
        except Exception as e:
            print(f"窗口关闭事件处理错误: {e}")
            event.accept()  # 确保窗口能关闭
    
    def load_tree_columns(self):
        """从文件加载自定义列配置"""
        try:
            if os.path.exists('tree_columns.json'):
                with open('tree_columns.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 加载默认列（如果有）
                    if 'default' in data:
                        self.tree_columns['default'] = data['default']
                    
                    # 加载自定义列
                    if 'custom' in data:
                        self.tree_columns['custom'] = data['custom']
                    
                    # 加载可见性设置
                    if 'visible' in data:
                        self.tree_columns['visible'] = data['visible']
                    else:
                        # 确保visible属性存在，并设置默认值
                        if 'visible' not in self.tree_columns:
                            self.tree_columns['visible'] = {}
                        
                        # 为默认列设置默认可见性
                        for col in self.tree_columns['default'][1:]:  # 跳过第一列（标签列）
                            if col not in self.tree_columns['visible']:
                                self.tree_columns['visible'][col] = True
        except Exception as e:
            print(f"加载列配置失败: {e}")
            # 确保visible属性存在
            if 'visible' not in self.tree_columns:
                self.tree_columns['visible'] = {}
                
            # 为默认列设置默认可见性
            for col in self.tree_columns['default'][1:]:  # 跳过第一列（标签列）
                if col not in self.tree_columns['visible']:
                    self.tree_columns['visible'][col] = True
    
    def save_tree_columns(self):
        """保存树视图列配置到文件"""
        try:
            # 保存到文件
            with open('tree_columns.json', 'w', encoding='utf-8') as f:
                json.dump(self.tree_columns, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存树列配置失败: {e}")
            
    def get_visible_columns(self):
        """获取当前可见的列，包括默认列和自定义列"""
        # 元素列始终可见
        columns = ['元素']
        
        # 添加可见的默认列
        for col in self.tree_columns['default'][1:]:  # 跳过元素列
            if self.tree_columns['visible'].get(col, True):
                columns.append(col)
        
        # 添加所有自定义列
        columns.extend(self.tree_columns['custom'])
        
        return columns
    
    def configure_tree_columns(self):
        """打开树列配置对话框"""
        dialog = ColumnConfigDialog(self, self.tree_columns)
        result = dialog.exec_()
        
        if result == QDialog.Accepted:
            # 更新树列配置
            self.tree_columns = dialog.get_config()
            
            # 保存配置到文件
            self.save_tree_columns()
            
            # 更新树视图
            visible_columns = self.get_visible_columns()
            self.tree_widget.setColumnCount(len(visible_columns))
            self.tree_widget.setHeaderLabels(visible_columns)
            
            # 使用新的刷新方法来更新列显示，而不是重新加载整个树
            if hasattr(self, 'root') and self.root is not None:
                self.refresh_tree_columns()
    
    def search_by_attribute(self):
        """根据属性名和值搜索元素"""
        attr_name = self.attr_name_input.text().strip()
        attr_value = self.attr_value_input.text().strip()
        
        if not attr_name and not attr_value:
            self.clear_attribute_search()
            return
            
        found_elements = []
        if self.root is not None:
            self.find_elements_by_attribute(self.root, attr_name, attr_value, found_elements)
        
        self.highlight_search_results(found_elements)
    
    def find_elements_by_attribute(self, element, attr_name, attr_value=None, found_elements=None):
        """递归查找具有指定属性的元素"""
        if found_elements is None:
            found_elements = []
        
        # 检查当前元素的属性
        if attr_name:
            if attr_name in element.attrib:
                if not attr_value or attr_value.lower() in element.attrib[attr_name].lower():
                    found_elements.append(element)
        elif attr_value:
            # 如果只指定了属性值，检查所有属性
            for value in element.attrib.values():
                if attr_value.lower() in value.lower():
                    found_elements.append(element)
                    break
        
        # 递归检查子元素
        for child in element:
            self.find_elements_by_attribute(child, attr_name, attr_value, found_elements)
        
        return found_elements
    
    def highlight_search_results(self, elements):
        """
        高亮显示搜索结果
        
        Args:
            elements: 要高亮的元素列表
        """
        if not hasattr(self, 'tree_items'):
            return
            
        # 清除所有现有高亮
        self.clear_all_highlighting()
            
        # 保存搜索结果
        self.search_result_elements = []
        valid_items = []
        
        if elements:  # 只在有搜索结果时进行高亮
            # 标记匹配项并展开其父节点
            for element in elements:
                # 跳过无效元素
                if element not in self.tree_items:
                    continue
                    
                tree_item = self.tree_items.get(element)
                if tree_item:
                    # 添加到有效结果列表
                    self.search_result_elements.append(element)
                    valid_items.append(tree_item)
                    
                    # 设置背景色以高亮显示
                    tree_item.setBackground(0, QColor(255, 255, 0, 100))  # 浅黄色背景
                    
                    # 确保项目可见（展开所有父节点）
                    self.ensure_item_visible(tree_item)
            
            # 如果有结果，选中第一个
            if valid_items:
                first_item = valid_items[0]
                self.tree_widget.setCurrentItem(first_item)
                self.tree_widget.scrollToItem(first_item)
    
    def clear_all_highlighting(self):
        """清除所有高亮显示"""
        # 清除代码视图中的高亮
        self.code_edit.setExtraSelections([])  # 使用空列表清除所有高亮
        
        # 清除树视图中的高亮
        root = self.tree_widget.invisibleRootItem()
        self._clear_item_highlighting(root)
    
    def _clear_item_highlighting(self, item):
        """递归清除树项目的高亮"""
        # 清除当前项目的背景色
        item.setBackground(0, QColor(Qt.transparent))
        
        # 递归处理子项目
        for i in range(item.childCount()):
            self._clear_item_highlighting(item.child(i))
    
    def find_tree_item_by_element(self, target_element):
        """
        根据元素查找对应的树项目
        
        Args:
            target_element: 目标元素
            
        Returns:
            找到的树项目，如果未找到则返回None
        """
        # 从根节点开始遍历
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            found_item = self._find_item_recursive(item, target_element)
            if found_item:
                return found_item
        
        return None
    
    def _find_item_recursive(self, item, target_element):
        """
        递归查找元素对应的树项目
        
        Args:
            item: 当前树项目
            target_element: 目标元素
            
        Returns:
            找到的树项目，如果未找到则返回None
        """
        # 检查当前项目是否对应目标元素
        if hasattr(item, 'element') and item.element is target_element:
            return item
        
        # 递归检查所有子项目
        for i in range(item.childCount()):
            child_item = item.child(i)
            found = self._find_item_recursive(child_item, target_element)
            if found:
                return found
        
        return None
    
    def ensure_item_visible(self, item):
        """
        确保树项目可见（展开所有父节点）
        
        Args:
            item: 要显示的树项目
        """
        # 展开所有父节点
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
    
    def clear_attribute_search(self):
        """清除属性搜索"""
        self.attr_name_input.clear()
        self.attr_value_input.clear()
        self.clear_search_highlighting()
    
    def toggle_autocomplete(self):
        """
        切换自动补全功能的启用状态
        """
        self.autocomplete_enabled = not self.autocomplete_enabled
        self.autocomplete_action.setChecked(self.autocomplete_enabled)
        
        # 更新属性表的委托
        self.setup_attr_table_completer()
        
        status = "启用" if self.autocomplete_enabled else "禁用"
        QMessageBox.information(self, "自动补全", f"已{status}属性自动补全功能")
    
    def manage_custom_attributes(self):
        """
        打开自定义属性管理对话框
        """
        dialog = AttributeManagementDialog(self, self.attr_completer)
        dialog.exec_()
    
    def setup_attr_table_completer(self):
        """
        设置属性表的自动补全
        """
        # 创建并设置属性表单元格编辑代理
        delegate = AttributeCompleterDelegate(
            parent=self.attr_table,
            attr_completer=self.attr_completer.get_attr_completer(),
            value_completer=self.attr_completer.get_value_completer(),
            enabled=self.autocomplete_enabled
        )
        
        # 设置属性名和属性值列的编辑代理
        self.attr_table.setItemDelegateForColumn(0, delegate)  # 属性名列
        self.attr_table.setItemDelegateForColumn(1, delegate)  # 属性值列
    
    def update_completers_from_xml(self):
        """
        从当前XML更新自动补全数据
        """
        if hasattr(self, 'root') and self.root is not None:
            # 提取属性值数据
            self.attr_completer.extract_attribute_values(self.root)
            
            # 更新属性名补全器模型以反映最新的属性列表
            attr_list = self.attr_completer.get_attribute_list()
            self.attr_completer.attr_completer.setModel(QStringListModel(attr_list))

    def on_attr_table_cell_activated(self, row, column):
        """
        当用户激活属性表单元格时（如双击开始编辑）
        
        Args:
            row: 行索引
            column: 列索引
        """
        try:
            print(f"单元格激活: 行={row}, 列={column}")
            
            # 如果自动补全被禁用，直接返回
            if not self.autocomplete_enabled:
                return
            
            # 确保表格有效
            if not hasattr(self, 'attr_table') or self.attr_table is None:
                print("属性表无效")
                return
                
            # 确保行列索引有效
            if row < 0 or column < 0 or row >= self.attr_table.rowCount() or column >= self.attr_table.columnCount():
                print(f"行列索引越界: row={row}, column={column}, rowCount={self.attr_table.rowCount()}, columnCount={self.attr_table.columnCount()}")
                return
            
            # 确保最新的XML数据被提取到补全器中
            if hasattr(self, 'root') and self.root is not None:
                try:
                    self.update_completers_from_xml()
                except Exception as e:
                    print(f"更新补全数据时发生错误: {e}")
            
            # 如果是属性值列，并且已经有属性名
            if column == 1 and row < self.attr_table.rowCount():
                try:
                    attr_name_item = self.attr_table.item(row, 0)
                    if attr_name_item and attr_name_item.text():
                        attr_name = attr_name_item.text()
                        print(f"正在为属性 '{attr_name}' 设置补全")
                        
                        # 更新属性值补全器，使用当前编辑的属性名
                        self.attr_completer.update_value_completer(attr_name)
                        
                        # 重新设置补全器到编辑器
                        try:
                            self.setup_attr_table_completer()
                        except Exception as e:
                            print(f"设置属性表补全器时发生错误: {e}")
                except Exception as e:
                    print(f"处理属性名时发生错误: {e}")
        except Exception as e:
            print(f"单元格激活处理时发生错误: {e}")

    def toggle_comments(self):
        """切换注释显示状态"""
        self.tree_widget.show_comments = self.show_comments_action.isChecked()
        self.update_tree_widget(save_expand_state=True)

    def on_file_changed(self, path):
        """处理文件变更事件"""
        # 检查文件是否存在（可能被删除）
        if not os.path.exists(path):
            return
            
        # 获取文件的最后修改时间
        current_time = os.path.getmtime(path)
        
        # 防止重复触发
        if current_time == self.last_modified_time:
            return
            
        self.last_modified_time = current_time
        
        try:
            # 创建状态管理器并保存当前状态
            tree_state = TreeStateManager(self.tree_widget).save_state()
            
            # 重新加载XML文件
            parser = etree.XMLParser(remove_blank_text=False, 
                                   remove_comments=False,
                                   remove_pis=False,
                                   strip_cdata=False)
            
            self.tree = etree.parse(path, parser)
            self.root = self.tree.getroot()
            
            # 更新UI，不保存展开状态
            self.update_tree_widget(save_expand_state=False)
            self.update_code_view()
            
            # 使用延迟调用恢复状态
            QTimer.singleShot(100, lambda: tree_state.restore_state())
            
            # 显示提示消息
            self.statusBar().showMessage('文件已更新', 3000)
            
        except Exception as e:
            QMessageBox.warning(self, '警告', f'重新加载文件失败: {str(e)}')
            print(f"重新加载文件失败: {e}")
            import traceback
            traceback.print_exc()

    def openFile(self):
        """打开XML文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, '打开XML文件', '', 'XML文件 (*.xml);;所有文件 (*)')
        
        if file_path:
            try:
                # 如果之前有监视的文件，先移除
                if self.current_file and self.current_file in self.file_watcher.files():
                    self.file_watcher.removePath(self.current_file)
                
                # 清除当前的搜索高亮等状态
                if hasattr(self, 'search_result_elements'):
                    self.clear_search_highlighting()
                
                # 创建保留空白和注释的解析器
                parser = etree.XMLParser(remove_blank_text=False, 
                                      remove_comments=False,
                                      remove_pis=False,
                                      strip_cdata=False)
                
                # 解析XML文件
                self.tree = etree.parse(file_path, parser)
                self.root = self.tree.getroot()
                
                # 保存原始文件内容以备后续比对
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.original_content = f.read()
                
                # 保存当前文件路径
                self.current_file = file_path
                
                # 添加文件到监视器
                self.file_watcher.addPath(file_path)
                self.last_modified_time = os.path.getmtime(file_path)
                
                # 加载文件关联的注释
                self.file_tabs.load_file_comments(file_path)
                
                # 更新UI，不保存展开状态
                self.update_tree_widget(save_expand_state=False)
                self.update_code_view()
                
                # 更新自动补全数据
                if self.autocomplete_enabled:
                    self.update_completers_from_xml()
                
                self.statusBar().showMessage(f'已加载文件: {file_path}')
            except Exception as e:
                error_msg = f'无法解析XML文件: {str(e)}'
                print(error_msg)
                import traceback
                traceback.print_exc()  # 输出详细错误信息
                QMessageBox.critical(self, '错误', error_msg)

    def save_undo_state(self):
        """保存当前状态到撤销栈"""
        if not self.tree:
            return
            
        try:
            # 将当前XML转换为字符串，但不包含XML声明
            xml_str = etree.tostring(self.root, 
                                   encoding='utf-8',
                                   xml_declaration=False,
                                   pretty_print=True,
                                   with_tail=True).decode('utf-8')
            
            # 将状态添加到撤销栈
            self.undo_stack.append(xml_str)
            
            # 如果撤销栈太大，移除最早的状态
            if len(self.undo_stack) > self.max_undo_steps:
                self.undo_stack.pop(0)
                
        except Exception as e:
            print(f"保存撤销状态失败: {e}")

    def undo_last_action(self):
        """撤销上一次操作"""
        if not self.undo_stack:
            self.statusBar().showMessage('没有可撤销的操作', 2000)
            return
            
        try:
            # 获取上一个状态
            previous_state = self.undo_stack.pop()
            
            # 添加XML声明
            xml_content = f'<?xml version="1.0" encoding="utf-8"?>\n{previous_state}'
            
            # 创建解析器
            parser = etree.XMLParser(remove_blank_text=False,
                                   remove_comments=False,
                                   remove_pis=False,
                                   strip_cdata=False)
            
            # 解析上一个状态
            self.tree = etree.parse(io.BytesIO(xml_content.encode('utf-8')), parser)
            self.root = self.tree.getroot()
            
            # 更新UI
            self.update_tree_widget(save_expand_state=True)
            self.update_code_view()
            
            self.statusBar().showMessage('已撤销上一次操作', 2000)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'撤销操作失败: {str(e)}')
            print(f"撤销操作失败: {e}")
            import traceback
            traceback.print_exc()

    def on_text_search_changed(self):
        """处理全局文本搜索变化"""
        search_text = self.text_search_input.text().strip()
        if not search_text:
            self.clear_text_search()
            return
            
        # 清除之前的高亮
        self.clear_all_highlighting()
            
        # 使用现有的搜索逻辑，但搜索所有属性和文本内容
        found_elements = []
        if self.root is not None:
            if self.fuzzy_search:  # 模糊搜索
                self._search_text_recursive_fuzzy(self.root, search_text.lower(), found_elements)
            else:  # 全字匹配搜索
                self._search_text_recursive_exact(self.root, search_text.lower(), found_elements)
        
        # 高亮显示搜索结果
        self.highlight_search_results(found_elements)

    def _search_text_recursive_fuzzy(self, element, search_text, found_elements):
        """递归模糊搜索文本内容"""
        try:
            # 检查是否是注释节点
            if isinstance(element, etree._Comment):
                if element.text and search_text in element.text.lower():
                    found_elements.append(element)
                return

            # 检查元素的文本内容
            if element.text and search_text in element.text.lower():
                found_elements.append(element)
                
            # 检查元素的属性值
            for value in element.attrib.values():
                if search_text in str(value).lower():
                    found_elements.append(element)
                    break
            
            # 检查元素的标签名
            if hasattr(element, 'tag') and isinstance(element.tag, str):
                if search_text in element.tag.lower():
                    found_elements.append(element)
            
            # 递归检查子元素
            for child in element:
                self._search_text_recursive_fuzzy(child, search_text, found_elements)
                
        except Exception as e:
            print(f"搜索文本时出错: {e}")

    def _search_text_recursive_exact(self, element, search_text, found_elements):
        """递归全字匹配搜索文本内容"""
        try:
            # 检查是否是注释节点
            if isinstance(element, etree._Comment):
                if element.text and search_text == element.text.lower():
                    found_elements.append(element)
                return

            # 检查元素的文本内容
            if element.text and search_text == element.text.lower():
                found_elements.append(element)
                
            # 检查元素的属性值
            for value in element.attrib.values():
                if search_text == str(value).lower():
                    found_elements.append(element)
                    break
            
            # 检查元素的标签名
            if hasattr(element, 'tag') and isinstance(element.tag, str):
                if search_text == element.tag.lower():
                    found_elements.append(element)
            
            # 递归检查子元素
            for child in element:
                self._search_text_recursive_exact(child, search_text, found_elements)
                
        except Exception as e:
            print(f"搜索文本时出错: {e}")

    def clear_text_search(self):
        """清除全局文本搜索"""
        self.text_search_input.clear()
        self.clear_search_highlighting()

    def search_in_tree(self):
        """在树视图中执行搜索"""
        search_text = self.search_input.text()
        search_type = self.search_type_combo.currentText()
        case_sensitive = self.case_sensitive_checkbox.isChecked()
        
        # 清除所有现有高亮
        self.clear_all_highlighting()
        
        # 如果搜索文本为空，直接返回
        if not search_text:
            self.status_bar.showMessage("请输入搜索内容")
            return
            
        # 查找匹配的元素
        found_elements = self.find_elements(search_text, search_type, case_sensitive)
        
        # 高亮匹配的元素
        highlight_color = QColor(255, 255, 0, 100)  # 浅黄色高亮
        for item in found_elements:
            item.setBackground(0, highlight_color)
            
        # 更新状态栏
        if found_elements:
            self.status_bar.showMessage(f"找到 {len(found_elements)} 个匹配项")
            # 选中并滚动到第一个匹配项
            self.tree_widget.setCurrentItem(found_elements[0])
            self.tree_widget.scrollToItem(found_elements[0])
        else:
            self.status_bar.showMessage("未找到匹配项")
            
    def on_search_type_changed(self):
        """搜索类型改变时的处理"""
        # 清除现有高亮并重新执行搜索
        self.clear_all_highlighting()
        self.search_in_tree()

    def find_elements(self, search_text, search_type, case_sensitive=False):
        """根据搜索条件查找元素"""
        elements = []
        root = self.tree_widget.invisibleRootItem()
        
        def search_recursive(item):
            # 获取项目文本
            item_text = item.text(0)
            
            # 根据大小写敏感设置进行比较
            if not case_sensitive:
                search_text_compare = search_text.lower()
                item_text_compare = item_text.lower()
            else:
                search_text_compare = search_text
                item_text_compare = item_text
            
            # 根据搜索类型进行匹配
            if search_type == "精确匹配":
                if item_text_compare == search_text_compare:
                    elements.append(item)
            elif search_type == "包含":
                if search_text_compare in item_text_compare:
                    elements.append(item)
            elif search_type == "正则表达式":
                try:
                    if re.search(search_text, item_text, flags=0 if case_sensitive else re.IGNORECASE):
                        elements.append(item)
                except re.error:
                    pass
            
            # 递归搜索子项目
            for i in range(item.childCount()):
                search_recursive(item.child(i))
        
        # 从根节点开始递归搜索
        for i in range(root.childCount()):
            search_recursive(root.child(i))
            
        return elements

    def toggle_search_mode(self):
        """切换搜索模式（模糊搜索/全字匹配）"""
        # 确保两个按钮状态互斥
        if self.sender() == self.fuzzy_search_btn:
            self.fuzzy_search = True
            self.exact_search_btn.setChecked(False)
        else:
            self.fuzzy_search = False
            self.fuzzy_search_btn.setChecked(False)
        
        # 重新执行搜索
        self.on_text_search_changed()

class CustomCompleter(QCompleter):
    """
    自定义补全器，支持复合表达式中的部分文本替换
    """
    def __init__(self, model=None, parent=None):
        super(CustomCompleter, self).__init__(model, parent)
        self.setCompletionMode(QCompleter.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterMode(Qt.MatchStartsWith)
        
        # 记录引用符号在表达式中的位置
        self.reference_start_pos = -1
        
        # 当补全器弹窗关闭时清理引用位置
        if self.popup():
            self.popup().hideEvent = lambda e: self._clean_up(e)
    
    def _clean_up(self, event):
        """弹窗隐藏时的清理工作"""
        try:
            # 重置引用位置
            self.reference_start_pos = -1
            
            # 调用原始的hideEvent（如果存在）
            original_hide = getattr(self.popup().__class__, 'hideEvent', None)
            if original_hide:
                original_hide(self.popup(), event)
        except Exception as e:
            print(f"补全器清理时发生错误: {e}")
    
    def splitPath(self, path):
        """
        自定义路径分割，只取最后一个引用符号后的内容
        """
        try:
            # 找到最后一个引用符号的位置
            last_hash_pos = max(path.rfind('#'), path.rfind('@'))
            if last_hash_pos >= 0:
                # 记录引用开始位置
                self.reference_start_pos = last_hash_pos
                # 返回引用符号后的文本作为过滤前缀
                return [path[last_hash_pos:]]
            return [path]
        except Exception as e:
            print(f"分割路径时发生错误: {e}")
            return [path]
    
    def pathFromIndex(self, index):
        """
        自定义从索引到路径的转换，返回完整的补全项
        """
        try:
            # 获取选中的补全项
            path = super(CustomCompleter, self).pathFromIndex(index)
            return path
        except Exception as e:
            print(f"获取补全路径时发生错误: {e}")
            return ""
    
    def complete(self, rect=None):
        """
        重写complete方法，添加额外的安全检查
        """
        try:
            # 检查当前控件是否有效
            widget = self.widget()
            if not widget or not widget.isVisible() or not widget.hasFocus():
                return False
                
            return super(CustomCompleter, self).complete(rect)
        except Exception as e:
            print(f"显示补全窗口时发生错误: {e}")
            return False

class CustomLineEdit(QLineEdit):
    """
    自定义文本编辑框，支持智能补全处理
    """
    def __init__(self, parent=None):
        super(CustomLineEdit, self).__init__(parent)
        self._completer = None
        self._is_valid = True  # 标记编辑器是否有效
        
        # 继承QLineEdit的信号
        self.returnPressed = self.returnPressed
        self.editingFinished = self.editingFinished
        
        # 监听焦点变化，在失去焦点时清理补全窗口
        self.focusChanged = QApplication.instance().focusChanged
        self.focusChanged.connect(self._handle_focus_change)
    
    def _handle_focus_change(self, old, now):
        """处理焦点变化，安全地清理补全窗口"""
        try:
            # 如果当前编辑器失去焦点
            if old is self and self._completer:
                # 隐藏补全弹窗
                popup = self._completer.popup()
                if popup and popup.isVisible():
                    popup.hide()
        except RuntimeError:
            # 防止对象已删除的情况
            pass
    
    def setCustomCompleter(self, completer):
        """设置自定义补全器"""
        if self._completer:
            try:
                self._completer.setWidget(None)
            except RuntimeError:
                # 如果补全器已经被删除，忽略错误
                pass
        
        self._completer = completer
        if self._completer:
            self._completer.setWidget(self)
            
            # 使用安全连接方式
            try:
                self._completer.activated.disconnect()  # 断开所有连接
            except (TypeError, RuntimeError):
                pass  # 忽略没有连接的情况
                
            self._completer.activated.connect(self._insertCompletion)
    
    def completer(self):
        """获取补全器"""
        return self._completer
    
    def _insertCompletion(self, completion):
        """
        处理补全项插入，支持复合表达式
        """
        try:
            # 安全检查
            if not self._is_valid or not self._completer or not isinstance(self._completer, CustomCompleter):
                return
            
            # 获取当前文本和光标位置
            text = self.text()
            cursor_pos = self.cursorPosition()
            
            # 从补全器获取引用开始位置
            ref_start = self._completer.reference_start_pos
            if ref_start >= 0 and ref_start < cursor_pos:
                # 构建新文本：保留前面的部分 + 新的补全文本 + 后面的部分
                new_text = (
                    text[:ref_start] +        # 引用符号之前的内容
                    completion +              # 选择的补全项
                    text[cursor_pos:]         # 光标后的内容
                )
                
                # 计算新的光标位置（应该位于补全项之后）
                new_cursor_pos = ref_start + len(completion)
                
                # 更新文本并设置光标位置
                self.setText(new_text)
                self.setCursorPosition(new_cursor_pos)
        except Exception as e:
            print(f"插入补全项时发生错误: {e}")
    
    def keyPressEvent(self, event):
        """
        处理键盘事件，支持自动补全触发
        """
        try:
            # 安全检查
            if not self._is_valid:
                super(CustomLineEdit, self).keyPressEvent(event)
                return
                
            # 如果补全器正在显示，让它处理按键事件
            if self._completer and self._completer.popup() and self._completer.popup().isVisible():
                # 这些键由补全器处理
                if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                    event.ignore()
                    return
            
            # 调用基类方法处理普通键盘输入
            super(CustomLineEdit, self).keyPressEvent(event)
            
            # 检查是否输入了#或@（需要触发补全）
            if self._completer and self.hasFocus():  # 确保编辑器有焦点
                try:
                    text = self.text()
                    if '#' in text or '@' in text:
                        # 显示补全弹窗
                        rect = self.rect()
                        self._completer.complete(rect)
                except RuntimeError:
                    # 防止对象已删除的情况
                    self._is_valid = False
            
            # 处理文本变化，触发补全更新
            self._updateCompletionPrefix()
        except Exception as e:
            print(f"键盘事件处理错误: {e}")
    
    def _updateCompletionPrefix(self):
        """
        更新补全器的前缀，使其始终显示正确的匹配项
        """
        try:
            # 安全检查
            if not self._is_valid or not self._completer or not self.hasFocus():
                return
            
            text = self.text()
            cursor_pos = self.cursorPosition()
            
            # 如果文本中包含引用符号
            if '#' in text or '@' in text:
                # 获取光标前的文本
                text_before_cursor = text[:cursor_pos]
                
                # 设置补全前缀为全文本，让CustomCompleter自己处理拆分
                self._completer.setCompletionPrefix(text_before_cursor)
                
                # 如果补全弹出窗口已经显示，更新它
                popup = self._completer.popup()
                if popup and popup.isVisible():
                    # 确保弹窗位置正确
                    cr = self.cursorRect()
                    cr.setWidth(self._completer.popup().sizeHintForColumn(0) + 
                                self._completer.popup().verticalScrollBar().sizeHint().width())
                    self._completer.complete(cr)
        except Exception as e:
            print(f"更新补全前缀时错误: {e}")
            self._is_valid = False
    
    def focusOutEvent(self, event):
        """处理失去焦点事件"""
        try:
            # 当编辑器失去焦点时，隐藏补全窗口
            if self._completer:
                popup = self._completer.popup()
                if popup and popup.isVisible():
                    popup.hide()
        except RuntimeError:
            # 防止对象已删除的情况
            self._is_valid = False
        
        super(CustomLineEdit, self).focusOutEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格，更现代的外观
    window = XMLEditorWindow()
    sys.exit(app.exec_()) 