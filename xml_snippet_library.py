import os
import json
from PyQt5.QtWidgets import (QWidget, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, 
                           QVBoxLayout, QInputDialog, QMessageBox, QMenu, QLabel, QDialog, 
                           QTextEdit, QDialogButtonBox, QLineEdit, QFormLayout, QTreeWidget, QTreeWidgetItem, QSizePolicy,
                           QFileDialog)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag, QIcon, QPixmap
from lxml import etree

class SnippetEditDialog(QDialog):
    """代码片段编辑对话框"""
    def __init__(self, name="", xml_content="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑代码片段")
        self.resize(600, 400)
        
        # 创建表单布局
        form_layout = QFormLayout()
        
        # 名称输入框
        self.name_edit = QLineEdit(name)
        form_layout.addRow("名称:", self.name_edit)
        
        # XML内容编辑框
        self.xml_edit = QTextEdit()
        self.xml_edit.setText(xml_content)
        self.xml_edit.setAcceptRichText(False)
        self.xml_edit.setLineWrapMode(QTextEdit.NoWrap)
        form_layout.addRow("XML内容:", self.xml_edit)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)
    
    def get_values(self):
        """获取对话框中的值"""
        return self.name_edit.text(), self.xml_edit.toPlainText()

class DraggableSnippetItem(QTreeWidgetItem):
    """可拖拽的代码片段列表项"""
    def __init__(self, name, xml_content):
        super().__init__([name])
        self.xml_content = xml_content
        self.setToolTip(0, xml_content[:200] + ("..." if len(xml_content) > 200 else ""))
        
        # 设置允许拖动
        self.setFlags(self.flags() | Qt.ItemIsDragEnabled)

class XMLSnippetLibrary(QWidget):
    """代码片段库组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None
        # 新的数据结构，支持分组
        self.groups = {
            "默认": {}  # 默认分组
        }
        self.current_group = "默认"  # 当前选中的分组
        
        # 设置策略，允许嵌入到分割器
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        self.init_ui()
        self.load_snippets()
    
    def set_main_window(self, window):
        """设置主窗口引用"""
        self.main_window = window
    
    def init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)  # 减小边距
        main_layout.setSpacing(2)  # 减小间距
        
        # 标题和搜索区域
        header_layout = QHBoxLayout()
        
        title_label = QLabel("代码片段库")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        # 添加搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索片段...")
        self.search_edit.textChanged.connect(self.filter_snippets)
        header_layout.addWidget(self.search_edit)
        
        main_layout.addLayout(header_layout)
        
        # 代码片段树视图
        self.snippet_tree = SnippetTreeWidget(self)
        self.snippet_tree.setHeaderLabels(["名称"])
        self.snippet_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.snippet_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.snippet_tree.setIndentation(15)  # 减小缩进
        self.snippet_tree.setAnimated(True)   # 启用动画效果
        self.snippet_tree.setSortingEnabled(True)  # 启用排序
        
        # 滚动功能配置
        self.snippet_tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.snippet_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.snippet_tree.setVerticalScrollMode(QTreeWidget.ScrollPerPixel)  # 平滑滚动
        
        main_layout.addWidget(self.snippet_tree, 1)  # 设置拉伸因子为1
        
        # 按钮区域 - 使用紧凑布局
        button_layout = QVBoxLayout()
        button_layout.setSpacing(2)  # 减小间距
        
        # 分组管理按钮
        group_button_layout = QHBoxLayout()
        group_button_layout.setSpacing(2)  # 减小间距
        
        self.add_group_btn = QPushButton("新建分组")
        self.add_group_btn.setFixedHeight(24)
        self.add_group_btn.clicked.connect(self.add_group)
        group_button_layout.addWidget(self.add_group_btn)
        
        self.rename_group_btn = QPushButton("重命名分组")
        self.rename_group_btn.setFixedHeight(24)
        self.rename_group_btn.clicked.connect(self.rename_group)
        group_button_layout.addWidget(self.rename_group_btn)
        
        self.delete_group_btn = QPushButton("删除分组")
        self.delete_group_btn.setFixedHeight(24)
        self.delete_group_btn.clicked.connect(self.delete_group)
        group_button_layout.addWidget(self.delete_group_btn)
        
        button_layout.addLayout(group_button_layout)
        
        # 片段管理按钮
        snippet_button_layout = QHBoxLayout()
        snippet_button_layout.setSpacing(2)  # 减小间距
        
        self.add_btn = QPushButton("添加片段")
        self.add_btn.setFixedHeight(24)
        self.add_btn.clicked.connect(self.add_snippet)
        snippet_button_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("编辑片段")
        self.edit_btn.setFixedHeight(24)
        self.edit_btn.clicked.connect(self.edit_snippet)
        snippet_button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("删除片段")
        self.delete_btn.setFixedHeight(24)
        self.delete_btn.clicked.connect(self.delete_snippet)
        snippet_button_layout.addWidget(self.delete_btn)
        
        button_layout.addLayout(snippet_button_layout)
        main_layout.addLayout(button_layout)
    
    def load_snippets(self):
        """从文件加载代码片段"""
        try:
            if os.path.exists('xml_snippets.json'):
                with open('xml_snippets.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 检查是否为新格式（包含分组）
                    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                        self.groups = data
                    else:
                        # 旧格式，将所有片段放入默认分组
                        self.groups = {"默认": data}
                    
                # 确保至少有默认分组
                if "默认" not in self.groups:
                    self.groups["默认"] = {}
                
                # 更新列表
                self.update_snippet_list()
        except Exception as e:
            print(f"加载代码片段失败: {e}")
            self.groups = {"默认": {}}
    
    def save_snippets(self):
        """保存代码片段到文件"""
        try:
            with open('xml_snippets.json', 'w', encoding='utf-8') as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存代码片段失败: {e}")
            QMessageBox.warning(self, "错误", f"保存代码片段失败: {e}")
    
    def update_snippet_list(self):
        """更新代码片段树视图"""
        self.snippet_tree.clear()
        group_items = {}
        
        # 首先添加所有分组
        for group_name in self.groups.keys():
            group_item = QTreeWidgetItem(self.snippet_tree, [group_name])
            group_item.setFlags(group_item.flags() | Qt.ItemIsDropEnabled)
            group_item.setExpanded(True)  # 默认展开分组
            group_item.setIcon(0, QIcon.fromTheme("folder"))
            
            # 设置字体为粗体
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            
            group_items[group_name] = group_item
        
        # 然后添加每个分组下的代码片段
        for group_name, snippets in self.groups.items():
            group_item = group_items.get(group_name)
            if group_item:
                for name, xml_content in snippets.items():
                    snippet_item = DraggableSnippetItem(name, xml_content)
                    snippet_item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                    group_item.addChild(snippet_item)
    
    def filter_snippets(self, text):
        """根据搜索文本过滤代码片段"""
        if not text:
            # 如果搜索框为空，显示所有项目
            for i in range(self.snippet_tree.topLevelItemCount()):
                group_item = self.snippet_tree.topLevelItem(i)
                group_item.setHidden(False)
                for j in range(group_item.childCount()):
                    group_item.child(j).setHidden(False)
            return
        
        # 转换为小写以进行不区分大小写的搜索
        search_text = text.lower()
        
        # 遍历所有分组和片段
        for i in range(self.snippet_tree.topLevelItemCount()):
            group_item = self.snippet_tree.topLevelItem(i)
            group_visible = False
            
            # 检查分组名称是否匹配
            if search_text in group_item.text(0).lower():
                group_visible = True
                # 显示该分组的所有子项
                for j in range(group_item.childCount()):
                    group_item.child(j).setHidden(False)
            else:
                # 检查该分组下的所有片段
                for j in range(group_item.childCount()):
                    snippet_item = group_item.child(j)
                    # 检查片段名称和内容
                    if search_text in snippet_item.text(0).lower() or (
                        hasattr(snippet_item, 'xml_content') and 
                        search_text in snippet_item.xml_content.lower()
                    ):
                        snippet_item.setHidden(False)
                        group_visible = True
                    else:
                        snippet_item.setHidden(True)
            
            # 设置分组可见性
            group_item.setHidden(not group_visible)
    
    def add_snippet(self):
        """添加新的代码片段"""
        # 获取当前选中的分组
        group_name = self.get_selected_group()
        if not group_name:
            group_name = "默认"  # 如果没有选中分组，使用默认分组
        
        dialog = SnippetEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            name, xml_content = dialog.get_values()
            
            # 验证名称和内容
            if not name.strip():
                QMessageBox.warning(self, "错误", "名称不能为空")
                return
                
            if not xml_content.strip():
                QMessageBox.warning(self, "错误", "XML内容不能为空")
                return
            
            # 验证XML内容 - 只检查格式合法性，不转换内容
            try:
                # 使用包装方式验证XML，避免解析错误
                wrapped_xml = f"<root>{xml_content}</root>"
                etree.fromstring(wrapped_xml)
            except Exception as e:
                # 如果解析失败，可能内容有问题，但也可能是包含多个顶级元素
                # 尝试逐行验证
                is_valid = True
                error_msg = str(e)
                
                try:
                    # 清理内容，移除注释，然后验证
                    import re
                    # 移除注释
                    cleaned_xml = re.sub(r'<!--.*?-->', '', xml_content, flags=re.DOTALL)
                    # 分割成单独的标签行
                    lines = cleaned_xml.splitlines()
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 如果是独立的自闭合标签，直接测试
                        if re.match(r'<[^>]+/>', line):
                            try:
                                etree.fromstring(line)
                            except Exception as tag_error:
                                is_valid = False
                                error_msg = str(tag_error)
                                break
                        # 如果看起来是开始标签，尝试与结束标签配对
                        elif '<' in line and '>' in line:
                            # 这里简化处理，实际上可能需要更复杂的逻辑
                            pass
                except:
                    # 如果清理和验证也失败，那么可能确实存在语法问题
                    pass
                
                if not is_valid:
                    QMessageBox.warning(self, "XML语法错误", f"XML内容无效: {error_msg}")
                    return
            
            # 检查在当前分组中名称是否已存在
            if name in self.groups[group_name]:
                result = QMessageBox.question(
                    self, "确认覆盖", 
                    f"在分组 '{group_name}' 中已存在名为 '{name}' 的代码片段，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if result != QMessageBox.Yes:
                    return
            
            # 添加到字典并更新列表
            self.groups[group_name][name] = xml_content
            self.update_snippet_list()
            self.save_snippets()
    
    def edit_snippet(self):
        """编辑选中的代码片段"""
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择一个代码片段")
            return
        
        selected_item = selected_items[0]
        # 检查是否是代码片段（非顶级项）
        if selected_item.parent() is None:
            QMessageBox.information(self, "提示", "请选择一个代码片段进行编辑")
            return
        
        # 获取分组和片段信息
        group_item = selected_item.parent()
        group_name = group_item.text(0)
        snippet_name = selected_item.text(0)
        
        # 获取代码片段内容
        xml_content = self.groups[group_name].get(snippet_name, "")
        
        dialog = SnippetEditDialog(snippet_name, xml_content, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_name, new_content = dialog.get_values()
            
            # 验证名称和内容
            if not new_name.strip():
                QMessageBox.warning(self, "错误", "名称不能为空")
                return
                
            if not new_content.strip():
                QMessageBox.warning(self, "错误", "XML内容不能为空")
                return
            
            # 验证XML内容 - 只检查格式合法性，不转换内容
            try:
                # 使用包装方式验证XML，避免解析错误
                wrapped_xml = f"<root>{new_content}</root>"
                etree.fromstring(wrapped_xml)
            except Exception as e:
                # 如果解析失败，可能内容有问题，但也可能是包含多个顶级元素
                # 尝试逐行验证
                is_valid = True
                error_msg = str(e)
                
                try:
                    # 清理内容，移除注释，然后验证
                    import re
                    # 移除注释
                    cleaned_xml = re.sub(r'<!--.*?-->', '', new_content, flags=re.DOTALL)
                    # 分割成单独的标签行
                    lines = cleaned_xml.splitlines()
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 如果是独立的自闭合标签，直接测试
                        if re.match(r'<[^>]+/>', line):
                            try:
                                etree.fromstring(line)
                            except Exception as tag_error:
                                is_valid = False
                                error_msg = str(tag_error)
                                break
                        # 如果看起来是开始标签，尝试与结束标签配对
                        elif '<' in line and '>' in line:
                            # 这里简化处理，实际上可能需要更复杂的逻辑
                            pass
                except:
                    # 如果清理和验证也失败，那么可能确实存在语法问题
                    pass
                
                if not is_valid:
                    QMessageBox.warning(self, "XML语法错误", f"XML内容无效: {error_msg}")
                    return
            
            # 如果名称变了，检查是否已存在
            if new_name != snippet_name and new_name in self.groups[group_name]:
                result = QMessageBox.question(
                    self, "确认覆盖", 
                    f"在分组 '{group_name}' 中已存在名为 '{new_name}' 的代码片段，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if result != QMessageBox.Yes:
                    return
            
            # 更新代码片段
            if new_name != snippet_name:
                # 删除旧的，添加新的
                del self.groups[group_name][snippet_name]
            
            self.groups[group_name][new_name] = new_content
            self.update_snippet_list()
            self.save_snippets()
    
    def delete_snippet(self):
        """删除选中的代码片段"""
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择一个代码片段")
            return
        
        selected_item = selected_items[0]
        # 检查是否是代码片段（非顶级项）
        if selected_item.parent() is None:
            QMessageBox.information(self, "提示", "请选择一个代码片段进行删除")
            return
        
        # 获取分组和片段信息
        group_item = selected_item.parent()
        group_name = group_item.text(0)
        snippet_name = selected_item.text(0)
        
        # 确认删除
        result = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除代码片段 '{snippet_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            # 删除代码片段
            del self.groups[group_name][snippet_name]
            self.update_snippet_list()
            self.save_snippets()
    
    def move_snippet_to_group(self, snippet_name, from_group, to_group):
        """将代码片段移动到另一个分组"""
        if from_group == to_group:
            return
        
        # 检查目标分组中是否已存在同名片段
        if snippet_name in self.groups[to_group]:
            result = QMessageBox.question(
                self, "确认覆盖", 
                f"在分组 '{to_group}' 中已存在名为 '{snippet_name}' 的代码片段，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                return False
        
        # 移动片段
        self.groups[to_group][snippet_name] = self.groups[from_group][snippet_name]
        del self.groups[from_group][snippet_name]
        self.update_snippet_list()
        self.save_snippets()
        return True
    
    def get_selected_group(self):
        """获取当前选中的分组名称"""
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            return None
        
        selected_item = selected_items[0]
        # 如果选中的是分组
        if selected_item.parent() is None:
            return selected_item.text(0)
        # 如果选中的是片段，返回其所属分组
        else:
            return selected_item.parent().text(0)
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            # 如果没有选中项，显示默认菜单
            menu = QMenu()
            add_group_action = menu.addAction("新建分组")
            add_snippet_action = menu.addAction("添加代码片段")
            
            action = menu.exec_(self.snippet_tree.mapToGlobal(position))
            if action == add_group_action:
                self.add_group()
            elif action == add_snippet_action:
                self.add_snippet()
            return
        
        selected_item = selected_items[0]
        menu = QMenu()
        
        if selected_item.parent() is None:
            # 选中的是分组
            group_name = selected_item.text(0)
            
            # 分组操作
            add_snippet_action = menu.addAction("添加代码片段")
            menu.addSeparator()
            
            rename_group_action = None
            delete_group_action = None
            
            # 默认分组不允许重命名或删除
            if group_name != "默认":
                rename_group_action = menu.addAction("重命名分组")
                delete_group_action = menu.addAction("删除分组")
            
            action = menu.exec_(self.snippet_tree.mapToGlobal(position))
            
            if action == add_snippet_action:
                self.add_snippet()
            elif action == rename_group_action:
                self.rename_group()
            elif action == delete_group_action:
                self.delete_group()
        
        else:
            # 选中的是代码片段
            group_item = selected_item.parent()
            group_name = group_item.text(0)
            snippet_name = selected_item.text(0)
            
            # 片段操作
            edit_action = menu.addAction("编辑片段")
            delete_action = menu.addAction("删除片段")
            
            # 添加移动到分组子菜单
            if len(self.groups) > 1:
                move_menu = menu.addMenu("移动到分组")
                move_actions = {}
                
                for g_name in self.groups.keys():
                    if g_name != group_name:  # 不显示当前分组
                        action = move_menu.addAction(g_name)
                        move_actions[action] = g_name
            
            action = menu.exec_(self.snippet_tree.mapToGlobal(position))
            
            if action == edit_action:
                self.edit_snippet()
            elif action == delete_action:
                self.delete_snippet()
            elif action in move_actions.keys():
                # 移动到选定分组
                to_group = move_actions[action]
                self.move_snippet_to_group(snippet_name, group_name, to_group)
    
    def add_group(self):
        """添加新分组"""
        group_name, ok = QInputDialog.getText(self, "新建分组", "请输入分组名称:")
        if ok and group_name.strip():
            # 检查分组名称是否已存在
            if group_name in self.groups:
                QMessageBox.warning(self, "错误", f"分组 '{group_name}' 已存在")
                return
            
            # 添加新分组
            self.groups[group_name] = {}
            self.update_snippet_list()
            self.save_snippets()
    
    def rename_group(self):
        """重命名分组"""
        # 获取当前选中的分组
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择一个分组")
            return
        
        selected_item = selected_items[0]
        # 检查是否是分组（顶级项）
        if selected_item.parent() is not None:
            QMessageBox.information(self, "提示", "请选择一个分组进行重命名")
            return
        
        old_name = selected_item.text(0)
        
        # 不允许重命名默认分组
        if old_name == "默认":
            QMessageBox.information(self, "提示", "不能重命名默认分组")
            return
        
        # 获取新名称
        new_name, ok = QInputDialog.getText(self, "重命名分组", 
                                          "请输入新的分组名称:", 
                                          QLineEdit.Normal, 
                                          old_name)
        
        if ok and new_name.strip() and new_name != old_name:
            # 检查新名称是否已存在
            if new_name in self.groups:
                QMessageBox.warning(self, "错误", f"分组 '{new_name}' 已存在")
                return
            
            # 重命名分组
            self.groups[new_name] = self.groups.pop(old_name)
            self.update_snippet_list()
            self.save_snippets()
    
    def delete_group(self):
        """删除分组"""
        # 获取当前选中的分组
        selected_items = self.snippet_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择一个分组")
            return
        
        selected_item = selected_items[0]
        # 检查是否是分组（顶级项）
        if selected_item.parent() is not None:
            QMessageBox.information(self, "提示", "请选择一个分组进行删除")
            return
        
        group_name = selected_item.text(0)
        
        # 不允许删除默认分组
        if group_name == "默认":
            QMessageBox.information(self, "提示", "不能删除默认分组")
            return
        
        # 确认删除
        result = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除分组 '{group_name}' 及其所有代码片段吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            # 删除分组
            del self.groups[group_name]
            self.update_snippet_list()
            self.save_snippets()

class SnippetTreeWidget(QTreeWidget):
    """代码片段树视图组件，支持拖放和分组"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.library = parent
        
        # 设置拖放属性
        self.setDragEnabled(True)
    
    def startDrag(self, supportedActions):
        """开始拖动操作"""
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        selected_item = selected_items[0]
        # 只允许拖动代码片段（子项），不允许拖动分组
        if selected_item.parent() is None:
            return
        
        # 获取代码片段内容
        if not hasattr(selected_item, 'xml_content'):
            return
        
        # 创建MIME数据
        mime_data = QMimeData()
        xml_content = selected_item.xml_content
        snippet_name = selected_item.text(0)  # 获取片段名称
        
        # 设置普通文本和XML类型数据
        mime_data.setText(xml_content)
        
        # 添加一个特殊的标记数据，表示这是代码片段库拖放的XML，带有原始格式
        # 添加片段名称到MIME数据，使用自定义格式
        snippet_data = f"<!--SNIPPET_NAME:{snippet_name}-->\n{xml_content}"
        mime_data.setData("application/x-xml-snippet", snippet_data.encode('utf-8'))
        
        # 同时设置标准XML MIME类型以保持兼容性
        mime_data.setData("application/xml", xml_content.encode('utf-8'))
        
        # 添加纯文本和HTML格式以增强兼容性
        mime_data.setData("text/plain", xml_content.encode('utf-8'))
        mime_data.setData("text/html", f"<pre>{xml_content}</pre>".encode('utf-8'))
        
        # 创建拖动对象
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # 设置拖动时的图标
        pixmap = QPixmap(self.viewport().size())
        pixmap.fill(Qt.transparent)
        drag.setPixmap(pixmap)
        
        # 执行拖动
        result = drag.exec_(Qt.CopyAction | Qt.MoveAction) 