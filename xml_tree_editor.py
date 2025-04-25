import sys
import uuid
import os
import mimetypes
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QAbstractItemView, QApplication, 
                            QToolTip, QLabel, QStyle)
from PyQt5.QtCore import Qt, QMimeData, QByteArray, QPoint, QRect, QSize, QUrl, QTimer
from PyQt5.QtGui import QDrag, QColor, QPainter, QPixmap, QIcon
from lxml import etree
from tree_state_manager import TreeStateManager

class XMLTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super(XMLTreeWidget, self).__init__(parent)
        
        # 启用拖放功能
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)  # 确保显示拖放指示器
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # 设置更明确的拖放指示器样式
        self.setStyleSheet("""
            QTreeWidget {
                show-decoration-selected: 1;
            }
            QTreeWidget::item:selected {
                background-color: #3399FF;
            }
            QTreeWidget::item:hover {
                background-color: #E5F3FF;
            }
            QTreeWidget::indicator:unchecked {
                image: url(none);
            }
        """)
        
        # 存储树项目和元素的映射关系
        self.item_element_map = {}
        self.main_window = None
        
        # 拖放视觉提示
        self.dropTipLabel = QLabel(self)
        self.dropTipLabel.setStyleSheet("""
            QLabel { 
                background-color: #FFFFCC; 
                border: 1px solid #999999; 
                border-radius: 3px; 
                padding: 4px;
                font-size: 10pt;
                font-weight: bold;
            }
        """)
        self.dropTipLabel.setAlignment(Qt.AlignCenter)
        self.dropTipLabel.setWordWrap(True)
        self.dropTipLabel.hide()
        
        # 辅助拖放指示线
        self.dropLineVisible = False
        self.dropLineRect = QRect()
        self.dropLineColor = QColor(0, 120, 215)  # 蓝色
        
        # 当前拖放操作类型
        self.currentDropOperation = ""
        
        # 注释显示开关
        self.show_comments = True
        
        # 注释文本颜色
        self.comment_color = QColor(0, 128, 0)  # 绿色
    
    def set_main_window(self, window):
        self.main_window = window
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super(XMLTreeWidget, self).mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # 准备XML数据
        xml_data = []
        for item in selected_items:
            if hasattr(item, 'element'):
                xml_str = etree.tostring(item.element, encoding='utf-8').decode('utf-8')
                xml_data.append(xml_str)
        
        mime_data.setText("\n".join(xml_data))
        mime_data.setData("application/xml", "\n".join(xml_data).encode('utf-8'))
        
        # 创建拖动时的预览图像
        pixmap = QPixmap(self.viewport().size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        for item in selected_items:
            rect = self.visualItemRect(item)
            self.itemDelegate().paint(painter, self.viewOptions(), self.indexFromItem(item))
            painter.fillRect(rect, QColor(0, 120, 215, 100))  # 半透明蓝色
        painter.end()
        
        # 存储原始元素的引用
        self.dragged_elements = []
        self.dragged_parents = []
        self.dragged_tags = []
        
        for item in selected_items:
            if hasattr(item, 'element'):
                element = item.element
                parent = element.getparent()
                self.dragged_elements.append(element)
                self.dragged_parents.append(parent)
                # 正确处理注释节点的标签名
                if isinstance(element, etree._Comment):
                    self.dragged_tags.append("注释")
                else:
                    self.dragged_tags.append(element.tag)
        
        drag.setMimeData(mime_data)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos() - self.viewport().pos())
        
        # 显示拖动提示
        element_names = ", ".join(self.dragged_tags)
        QToolTip.showText(self.mapToGlobal(event.pos()), 
                         f"拖动: {element_names}",
                         self, self.rect(), 2000)
        
        result = drag.exec_(Qt.MoveAction | Qt.CopyAction)
    
    def dragEnterEvent(self, event):
        # 接受XML文本
        if event.mimeData().hasFormat("application/xml") or event.mimeData().hasText():
            event.acceptProposedAction()
        # 接受图片文件
        elif event.mimeData().hasUrls():
            # 检查是否含有图片文件
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if self.is_image_file(file_path):
                    event.acceptProposedAction()
                    return
            event.ignore()
        else:
            event.ignore()
    
    def is_image_file(self, file_path):
        """检查文件是否为图片文件"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in image_extensions
    
    def dragMoveEvent(self, event):
        # 处理XML或文本拖放
        if event.mimeData().hasFormat("application/xml") or event.mimeData().hasText():
            if not (event.mimeData().hasFormat("application/xml") or event.mimeData().hasText()):
                event.ignore()
                return
            
            # 获取拖放位置的项目
            drop_item = self.itemAt(event.pos())
            
            if not drop_item or not hasattr(drop_item, 'element'):
                self.dropTipLabel.hide()
                self.dropLineVisible = False
                self.viewport().update()
                event.acceptProposedAction()
                return
            
            # 获取项目在视图中的矩形区域
            item_rect = self.visualItemRect(drop_item)
            
            # 计算鼠标与项目的相对位置
            rel_pos = event.pos()
            
            # 确定拖放位置（上方、中间、下方）
            item_top = item_rect.top()
            item_height = item_rect.height()
            
            # 拖放指示区域为项目高度的25%
            drop_zone_size = item_height / 4
            
            if rel_pos.y() < item_top + drop_zone_size:
                # 上方区域 - 在元素前插入
                drop_position = QAbstractItemView.AboveItem
                self.currentDropOperation = "above"
                self.dropLineVisible = True
                self.dropLineRect = QRect(0, item_rect.top(), self.viewport().width(), 2)
                tip_text = "插入到此元素前"
            elif rel_pos.y() >= item_top + item_height - drop_zone_size:
                # 下方区域 - 在元素后插入
                drop_position = QAbstractItemView.BelowItem
                self.currentDropOperation = "below"
                self.dropLineVisible = True
                self.dropLineRect = QRect(0, item_rect.bottom(), self.viewport().width(), 2)
                tip_text = "插入到此元素后"
            else:
                # 中间区域 - 放入元素或创建新组
                drop_position = QAbstractItemView.OnItem
                self.currentDropOperation = "on"
                self.dropLineVisible = False
                
                drop_element = drop_item.element
                if drop_element.tag == "Group":
                    tip_text = "添加到组内"
                else:
                    tip_text = "创建新组"
            
            # 更新样式和提示
            if drop_position == QAbstractItemView.OnItem:
                drop_element = drop_item.element
                # 高亮显示目标项
                if drop_element.tag == "Group":
                    # 如果拖到Group上，使用绿色背景
                    drop_item.setBackground(0, QColor(204, 255, 204))  # 淡绿色
                else:
                    # 如果拖到其他元素上，使用黄色背景表示将创建新组
                    drop_item.setBackground(0, QColor(255, 255, 204))  # 淡黄色
            else:
                # 重置其他项的背景
                for i in range(self.topLevelItemCount()):
                    self.resetItemBackground(self.topLevelItem(i))
            
            # 将提示标签置于鼠标位置附近
            tip_pos = self.viewport().mapToGlobal(event.pos()) + QPoint(15, 15)
            self.dropTipLabel.setText(tip_text)
            self.dropTipLabel.adjustSize()
            self.dropTipLabel.move(self.viewport().mapFromGlobal(tip_pos))
            self.dropTipLabel.show()
            
            # 刷新视图以显示拖放线
            self.viewport().update()
            
            # 强制使用我们自己计算的拖放位置
            event.acceptProposedAction()
        # 处理图片文件拖放
        elif event.mimeData().hasUrls():
            # 检查是否含有图片文件
            has_image = False
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if self.is_image_file(file_path):
                    has_image = True
                    break
            
            if has_image:
                # 获取拖放位置的项目
                drop_item = self.itemAt(event.pos())
                
                if not drop_item:
                    # 如果没有项目在光标下，可能是拖到了根元素或空白区域
                    event.acceptProposedAction()
                    return
                
                # 获取项目在视图中的矩形区域
                item_rect = self.visualItemRect(drop_item)
                
                # 计算鼠标与项目的相对位置
                rel_pos = event.pos()
                
                # 确定拖放位置（上方、中间、下方）
                item_top = item_rect.top()
                item_height = item_rect.height()
                
                # 拖放指示区域为项目高度的25%
                drop_zone_size = item_height / 4
                
                if rel_pos.y() < item_top + drop_zone_size:
                    # 上方区域 - 在元素前插入
                    self.currentDropOperation = "above"
                    self.dropLineVisible = True
                    self.dropLineRect = QRect(0, item_rect.top(), self.viewport().width(), 2)
                    tip_text = "在此元素前插入图片"
                elif rel_pos.y() >= item_top + item_height - drop_zone_size:
                    # 下方区域 - 在元素后插入
                    self.currentDropOperation = "below"
                    self.dropLineVisible = True
                    self.dropLineRect = QRect(0, item_rect.bottom(), self.viewport().width(), 2)
                    tip_text = "在此元素后插入图片"
                else:
                    # 中间区域 - 放入元素
                    self.currentDropOperation = "on"
                    self.dropLineVisible = False
                    tip_text = "添加图片为此元素的子元素"
                
                # 更新提示
                tip_pos = self.viewport().mapToGlobal(event.pos()) + QPoint(15, 15)
                self.dropTipLabel.setText(tip_text)
                self.dropTipLabel.adjustSize()
                self.dropTipLabel.move(self.viewport().mapFromGlobal(tip_pos))
                self.dropTipLabel.show()
                
                # 刷新视图以显示拖放线
                self.viewport().update()
                
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
            return
    
    def resetItemBackground(self, item):
        """递归重置所有项的背景颜色"""
        item.setBackground(0, QColor(0, 0, 0, 0))  # 透明背景
        for i in range(item.childCount()):
            self.resetItemBackground(item.child(i))
    
    def paintEvent(self, event):
        super(XMLTreeWidget, self).paintEvent(event)
        
        # 绘制拖放指示线
        if self.dropLineVisible and not self.dropLineRect.isNull():
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 设置线条样式
            pen = painter.pen()
            pen.setColor(self.dropLineColor)
            pen.setWidth(2)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            
            # 绘制水平线
            painter.drawLine(self.dropLineRect.left() + 5, 
                            self.dropLineRect.top() + 1,
                            self.dropLineRect.right() - 5, 
                            self.dropLineRect.top() + 1)
            
            # 绘制小三角形指示器
            triangle_size = 6
            if self.currentDropOperation == "above":
                # 向上的三角形
                painter.setBrush(self.dropLineColor)
                points = [
                    QPoint(30, self.dropLineRect.top() + 1 - triangle_size),
                    QPoint(30 - triangle_size, self.dropLineRect.top() + 1),
                    QPoint(30 + triangle_size, self.dropLineRect.top() + 1)
                ]
                painter.drawPolygon(points)
            elif self.currentDropOperation == "below":
                # 向下的三角形
                painter.setBrush(self.dropLineColor)
                points = [
                    QPoint(30, self.dropLineRect.top() + 1 + triangle_size),
                    QPoint(30 - triangle_size, self.dropLineRect.top() + 1),
                    QPoint(30 + triangle_size, self.dropLineRect.top() + 1)
                ]
                painter.drawPolygon(points)
    
    def dragLeaveEvent(self, event):
        # 隐藏提示并重置样式
        self.dropTipLabel.hide()
        self.dropLineVisible = False
        
        # 重置所有项的背景
        for i in range(self.topLevelItemCount()):
            self.resetItemBackground(self.topLevelItem(i))
        
        self.viewport().update()
        super(XMLTreeWidget, self).dragLeaveEvent(event)
    
    def dropEvent(self, event):
        """处理拖放事件"""
        # 隐藏提示并重置样式
        self.dropTipLabel.hide()
        self.dropLineVisible = False
        
        # 重置背景颜色
        for i in range(self.topLevelItemCount()):
            self.resetItemBackground(self.topLevelItem(i))
        
        # 保存树视图状态
        self.state_manager = TreeStateManager(self)
        self.state_manager.save_state()
        
        # 处理图片文件拖放
        if event.mimeData().hasUrls():
            # 检查是否含有图片文件
            image_files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if self.is_image_file(file_path):
                    image_files.append(file_path)
            
            if image_files:
                # 处理图片拖放逻辑
                self.handle_image_drop(event, image_files)
                return
        
        # 获取拖放位置的项目和位置
        drop_item = self.itemAt(event.pos())
        
        if not drop_item or not hasattr(drop_item, 'element'):
            event.ignore()
            return
        
        # 首先确定拖放指示器的位置
        if self.currentDropOperation == "above":
            drop_indicator = QAbstractItemView.AboveItem
        elif self.currentDropOperation == "below":
            drop_indicator = QAbstractItemView.BelowItem
        else:
            drop_indicator = QAbstractItemView.OnItem
        
        # 获取XML数据以备创建新元素使用
        xml_data = ""
        is_snippet = False
        snippet_name = ""  # 初始化片段名称变量
        
        # 处理拖放
        try:
            # 尝试处理XML或文本数据
            if (event.mimeData().hasFormat("application/xml") or 
                event.mimeData().hasText()):
                
                # 如果有特定标记，表示这是代码片段拖放
                if (event.mimeData().hasFormat("application/x-xml-snippet") or 
                    (event.mimeData().hasText() and 
                    event.mimeData().text().startswith("<!--SNIPPET:"))):
                    
                    is_snippet = True
                    if event.mimeData().hasFormat("application/x-xml-snippet"):
                        # 优先使用专用MIME类型中的数据
                        snippet_data = event.mimeData().data("application/x-xml-snippet").data().decode('utf-8')
                        
                        # 提取片段名称
                        if "<!--SNIPPET_NAME:" in snippet_data:
                            name_start = snippet_data.find("<!--SNIPPET_NAME:") + len("<!--SNIPPET_NAME:")
                            name_end = snippet_data.find("-->", name_start)
                            if name_end > name_start:
                                snippet_name = snippet_data[name_start:name_end].strip()
                                # 从数据中移除片段名称注释
                                xml_data = snippet_data[name_end + 3:].strip()
                        else:
                            xml_data = snippet_data
                    else:
                        # 退回到文本格式
                        xml_data = event.mimeData().text()
                        if xml_data.startswith("<!--SNIPPET:"):
                            # 从注释中提取实际XML
                            start = xml_data.find("-->") + 3
                            xml_data = xml_data[start:].strip()
                else:
                    # 普通XML拖放
                    xml_data = (event.mimeData().data("application/xml").data().decode('utf-8') 
                               if event.mimeData().hasFormat("application/xml") 
                               else event.mimeData().text())
            
            # 如果没有数据，返回
            if not xml_data:
                event.ignore()
                return
            
            # 获取目标元素和其父元素
            drop_element = drop_item.element
            drop_parent = drop_element.getparent()
            
            # 特殊处理：如果是XML片段拖放
            if is_snippet:
                # 处理片段XML数据，解析并插入
                snippet_elements = []
                added_elements = []  # 用于跟踪添加的元素
                
                # 解析XML片段（可能包含多个元素）
                xml_parser = etree.XMLParser(remove_blank_text=False)
                try:
                    # 首先尝试解析为单个元素
                    snippet_element = etree.fromstring(xml_data, xml_parser)
                    snippet_elements.append(snippet_element)
                except etree.XMLSyntaxError:
                    # 如果不是单个元素，尝试包装并解析为多个元素
                    try:
                        wrapped_xml = f"<root>{xml_data}</root>"
                        root = etree.fromstring(wrapped_xml, xml_parser)
                        snippet_elements = list(root)
                    except Exception as wrap_error:
                        print(f"解析代码片段失败: {wrap_error}")
                        event.ignore()
                        return
                
                # 如果解析成功，执行插入操作
                if snippet_elements:
                    # 根据拖放位置确定插入逻辑
                    if drop_indicator == QAbstractItemView.OnItem:
                        # 拖到元素上方 - 作为子元素添加
                        for snippet in snippet_elements:
                            # 确保元素有换行符
                            snippet.tail = "\n"
                            drop_element.append(snippet)
                            added_elements.append(snippet)
                    
                    elif drop_indicator == QAbstractItemView.BelowItem:
                        # 拖到元素下方 - 作为同级元素插入
                        if drop_parent is not None:
                            # 获取目标元素在父元素中的索引
                            idx = drop_parent.index(drop_element) + 1
                            
                            # 从后往前插入，保持原始顺序
                            for snippet in reversed(snippet_elements):
                                # 确保元素有换行符
                                snippet.tail = "\n"
                                drop_parent.insert(idx, snippet)
                                added_elements.append(snippet)
                    
                    elif drop_indicator == QAbstractItemView.AboveItem:
                        # 拖到元素上方 - 作为同级元素插入
                        if drop_parent is not None:
                            # 获取目标元素在父元素中的索引
                            idx = drop_parent.index(drop_element)
                            
                            # 从后往前插入，保持原始顺序
                            for snippet in reversed(snippet_elements):
                                # 确保元素有换行符
                                snippet.tail = "\n"
                                drop_parent.insert(idx, snippet)
                                added_elements.append(snippet)
                
                # 更新UI
                if self.main_window:
                    self.main_window.update_tree_widget(save_expand_state=False)
                    
                    # 如果有片段名称，将其添加为作用注释
                    if snippet_name and added_elements and hasattr(self.main_window, 'file_tabs'):
                        for element in added_elements:
                            self.main_window.file_tabs.add_comment(
                                self.main_window.current_file, 
                                element, 
                                snippet_name
                            )
                        
                        # 刷新树视图的注释显示，确保立即显示注释
                        if hasattr(self.main_window, 'refresh_tree_comments'):
                            self.main_window.refresh_tree_comments()
                    
                    # 更新代码视图
                    self.main_window.update_code_view()
                    
                    # 延迟恢复树视图状态，确保树视图已经完全刷新
                    QTimer.singleShot(100, self._delayed_restore_state)
                
                # 接受事件
                event.acceptProposedAction()
                return
            
            # 如果是内部元素拖放，而且已经有元素引用
            if hasattr(self, 'dragged_elements') and self.dragged_elements:
                # 根据拖放指示器的位置，执行不同的操作
                if drop_indicator == QAbstractItemView.OnItem:
                    # 拖到元素上方 - 作为子元素添加
                    
                    # 如果目标元素是被拖动元素之一，阻止操作
                    if drop_element in self.dragged_elements:
                        event.ignore()
                        return
                    
                    # 一个个地添加拖动元素到目标元素中
                    for element in self.dragged_elements:
                        if element.getparent() is not None:
                            element.getparent().remove(element)
                        
                        # 确保元素有换行符
                        element.tail = "\n"
                        
                        # 添加到目标元素
                        drop_element.append(element)
                
                elif drop_indicator == QAbstractItemView.BelowItem:
                    # 拖到元素下方 - 作为同级元素插入
                    if drop_parent is not None:
                        # 获取目标元素在父元素中的索引
                        target_idx = drop_parent.index(drop_element) + 1
                        
                        # 特殊处理：如果是Group移动到Group相邻位置
                        is_group_to_group = False
                        if any(elem.tag == "Group" for elem in self.dragged_elements) and drop_element.tag == "Group":
                            is_group_to_group = True
                        
                        # 一个一个地添加拖动元素，注意索引会随着插入变化
                        for element in self.dragged_elements:
                            if element.getparent() is not None:
                                # 如果元素的当前位置在目标位置之前，需要调整目标索引
                                if element.getparent() == drop_parent:
                                    curr_idx = drop_parent.index(element)
                                    if curr_idx < target_idx:
                                        target_idx -= 1
                                element.getparent().remove(element)
                            
                            # 确保元素有换行符
                            element.tail = "\n"
                            
                            # 插入到正确位置
                            drop_parent.insert(target_idx, element)
                            target_idx += 1
                
                elif drop_indicator == QAbstractItemView.AboveItem:
                    # 拖到元素上方 - 作为同级元素插入
                    if drop_parent is not None:
                        # 获取目标元素在父元素中的索引
                        target_idx = drop_parent.index(drop_element)
                        
                        # 特殊处理：如果是Group移动到Group相邻位置
                        is_group_to_group = False
                        if any(elem.tag == "Group" for elem in self.dragged_elements) and drop_element.tag == "Group":
                            is_group_to_group = True
                        
                        # 反向添加元素，保持拖动元素的相对顺序
                        for element in reversed(self.dragged_elements):
                            if element.getparent() is not None:
                                # 如果元素的当前位置在目标位置之前，需要调整目标索引
                                if element.getparent() == drop_parent:
                                    curr_idx = drop_parent.index(element)
                                    if curr_idx < target_idx:
                                        target_idx -= 1
                                element.getparent().remove(element)
                            
                            # 确保元素有换行符
                            element.tail = "\n"
                            
                            # 插入到正确位置
                            drop_parent.insert(target_idx, element)
            
                # 更新旧路径和元素的映射
                old_paths = {}
                try:
                    # 尝试更新文件注释映射
                    self.update_comment_mappings(old_paths)
                except Exception as e:
                    print(f"更新注释映射失败: {e}")
            
                # 更新UI
                if self.main_window:
                    self.main_window.update_tree_widget(save_expand_state=False)
                    self.main_window.update_code_view()
                    
                    # 刷新树视图的注释显示
                    if hasattr(self.main_window, 'refresh_tree_comments'):
                        self.main_window.refresh_tree_comments()
                    
                    # 延迟恢复树视图状态
                    QTimer.singleShot(100, self._delayed_restore_state)
                
                event.acceptProposedAction()
                
                # 清除拖动元素引用
                self.dragged_elements = []
                self.dragged_parents = []
                return
            
        except Exception as e:
            print(f"处理拖放操作失败: {e}")
            import traceback
            traceback.print_exc()
            event.ignore()
            
        # 在处理完drop事件后，强制刷新树结构和列显示
        if self.main_window and hasattr(self.main_window, 'refresh_tree_columns'):
            self.main_window.refresh_tree_columns()
        elif self.main_window:
            # 如果没有专门的刷新列方法，则完全重建树视图
            self.main_window.update_tree_widget(save_expand_state=False)
            
        # 延迟恢复树视图状态
        QTimer.singleShot(100, self._delayed_restore_state)
    
    def _delayed_restore_state(self):
        """延迟恢复树视图状态，确保在UI刷新后执行"""
        if hasattr(self, 'state_manager'):
            self.state_manager.restore_state()
            
            # 恢复状态后也刷新注释
            if self.main_window and hasattr(self.main_window, 'refresh_tree_comments'):
                self.main_window.refresh_tree_comments()
    
    def update_comment_mappings(self, old_paths):
        """更新元素拖放后的注释映射 - 在新系统中仅刷新注释显示"""
        # 在基于ID的注释系统中，不需要更新路径映射
        # 仅需要刷新树视图的注释显示
        if self.main_window and hasattr(self.main_window, 'refresh_tree_comments'):
            self.main_window.refresh_tree_comments()

    def handle_image_drop(self, event, image_files):
        """处理图片拖放逻辑，创建Image元素"""
        if not self.main_window or not hasattr(self.main_window, 'current_file'):
            event.ignore()
            return
        
        # 保存树视图状态
        self.state_manager = TreeStateManager(self)
        self.state_manager.save_state()
        
        # 获取当前XML文件的目录
        xml_dir = os.path.dirname(self.main_window.current_file)
        if not xml_dir:
            event.ignore()
            return
        
        # 获取拖放位置的项目和位置
        drop_item = self.itemAt(event.pos())
        
        if not drop_item or not hasattr(drop_item, 'element'):
            event.ignore()
            return
        
        # 确定拖放的父元素和位置
        drop_element = drop_item.element
        drop_parent = drop_element.getparent()
        
        # 如果拖放到元素中间，则添加为子元素
        if self.currentDropOperation == "on":
            parent_element = drop_element
            insert_index = len(list(parent_element))
        else:
            parent_element = drop_parent
            if parent_element is None:
                event.ignore()
                return
            
            # 确定插入位置
            if self.currentDropOperation == "above":
                insert_index = parent_element.index(drop_element)
            else:  # below
                insert_index = parent_element.index(drop_element) + 1
        
        # 为每张图片创建Image元素
        for img_path in image_files:
            # 将图片路径转换为相对于XML文件的路径
            rel_path = os.path.relpath(img_path, xml_dir)
            # 统一使用正斜杠表示路径
            rel_path = rel_path.replace('\\', '/')
            
            # 创建Image元素
            img_element = etree.Element("Image")
            img_element.set("x", "")
            img_element.set("y", "")
            img_element.set("src", rel_path)
            
            # 添加换行符
            img_element.tail = "\n"
            if insert_index == 0 and parent_element.tag == self.main_window.root.tag:
                # 如果是添加到根元素开头，确保在元素前也有换行
                img_element.text = "\n"
            
            # 插入到XML树中
            parent_element.insert(insert_index, img_element)
            insert_index += 1
        
        # 更新UI
        if self.main_window:
            self.main_window.update_tree_widget(save_expand_state=False)
            self.main_window.update_code_view()
            
            # 刷新树视图的注释显示
            if hasattr(self.main_window, 'refresh_tree_comments'):
                self.main_window.refresh_tree_comments()
            
            # 延迟恢复树视图状态
            QTimer.singleShot(100, self._delayed_restore_state)
        
        # 刷新视图
        self.viewport().update()
        event.acceptProposedAction()

# 修改TreeItem类，以支持拖放
class DraggableTreeItem(QTreeWidgetItem):
    def __init__(self, parent, element, base_dir=None):
        super(DraggableTreeItem, self).__init__(parent)
        self.element = element
        self.base_dir = base_dir
        
        # 设置标签文本
        if isinstance(element, etree._Comment):
            self.setText(0, element.text.strip())
        else:
            self.setText(0, element.tag)
        
        # 设置拖放标志
        self.setFlags(self.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
    
    def __lt__(self, other):
        """比较函数，用于排序"""
        # 如果两个都是注释节点，保持原有顺序
        if (isinstance(self.element, etree._Comment) and 
            isinstance(other.element, etree._Comment)):
            return False
        
        # 如果只有一个是注释节点，注释节点应该跟随其相邻的元素
        if isinstance(self.element, etree._Comment):
            return False
        if isinstance(other.element, etree._Comment):
            return True
        
        # 如果都是普通元素，按标签名排序
        return self.text(0) < other.text(0) 