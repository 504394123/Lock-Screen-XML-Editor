"""
修复XMLTreeWidget类中右键菜单删除功能的补丁

此补丁提供了如何修改XMLTreeWidget类中的右键菜单删除功能，
以保持树视图的展开状态。
"""

# 在XMLTreeWidget类中添加以下代码

from tree_state_manager import TreeStateManager
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMenu, QAction, QMessageBox

class XMLTreeWidget(QTreeWidget):
    # 现有的类定义...
    
    def contextMenuEvent(self, event):
        """处理右键菜单事件"""
        # 获取右键点击位置的树项目
        item = self.itemAt(event.pos())
        if not item:
            return
            
        # 创建右键菜单
        menu = QMenu(self)
        
        # 添加删除操作
        delete_action = menu.addAction("删除元素")
        # 添加其他菜单项...
        
        # 执行菜单并获取选择的操作
        action = menu.exec_(event.globalPos())
        
        # 处理删除操作
        if action == delete_action:
            self.delete_selected_elements()
    
    def delete_selected_elements(self):
        """删除选中的XML元素，保持树状态"""
        # 获取选中的项目
        selected_items = self.selectedItems()
        if not selected_items:
            return
            
        # 确认是否删除
        result = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除选中的{len(selected_items)}个元素吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result != QMessageBox.Yes:
            return
            
        # 保存树状态
        state_manager = TreeStateManager(self)
        state_manager.save_state()
        
        # 执行删除操作
        for item in selected_items:
            if hasattr(item, 'element'):
                element = item.element
                parent = element.getparent()
                
                if parent is not None:
                    # 从XML树中移除元素
                    parent.remove(element)
        
        # 更新UI
        if self.main_window:
            self.main_window.update_tree_widget(save_expand_state=True)
            self.main_window.update_code_view()
            
            # 延迟恢复树状态
            QTimer.singleShot(100, lambda: state_manager.restore_state())
