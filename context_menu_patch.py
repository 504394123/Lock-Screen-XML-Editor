"""
修复结构树视图右键删除按钮导致折叠状态重置的问题

此补丁提供了如何修改右键菜单中删除功能的指导。
"""

from tree_state_manager import TreeStateManager
from PyQt5.QtCore import QTimer

# 在您的主窗口类或处理右键菜单的类中找到删除元素的方法
# 通常命名为delete_element、remove_element等

def delete_element(self):
    """
    删除选中的XML元素
    """
    # 获取当前选中的元素
    selected_items = self.tree_widget.selectedItems()
    if not selected_items:
        return
    
    # 保存树状态 - 在删除操作前
    tree_state = TreeStateManager(self.tree_widget).save_state()
    
    # 原有的删除逻辑
    for item in selected_items:
        if hasattr(item, 'element'):
            # 获取元素及其父元素
            element = item.element
            parent = element.getparent()
            
            if parent is not None:
                # 从XML树中移除元素
                parent.remove(element)
                
                # 从树视图中移除项目(如果需要)
                parent_item = item.parent()
                if parent_item:
                    index = parent_item.indexOfChild(item)
                    parent_item.takeChild(index)
                else:
                    # 如果是顶层项目
                    index = self.tree_widget.indexOfTopLevelItem(item)
                    self.tree_widget.takeTopLevelItem(index)
    
    # 更新XML代码视图
    if hasattr(self, 'update_code_view'):
        self.update_code_view()
    
    # 延迟恢复状态，确保UI已完全更新
    QTimer.singleShot(100, lambda: tree_state.restore_state())

# 另一种实现方式是使用辅助方法，适用于更复杂的操作
def delete_element_with_helper(self):
    """
    使用辅助方法删除元素并保持树状态
    """
    def perform_delete():
        selected_items = self.tree_widget.selectedItems()
        for item in selected_items:
            if hasattr(item, 'element'):
                # 删除元素逻辑
                element = item.element
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    
                # 可能还需要更新UI
                if hasattr(self, 'update_code_view'):
                    self.update_code_view()
    
    # 使用辅助方法保存状态、执行操作并恢复状态
    self.save_and_restore_tree_state(perform_delete)

"""
如何集成到您的代码中:

1. 找到处理右键菜单中删除操作的方法
2. 在删除操作前保存树状态
3. 执行删除操作
4. 延迟恢复树状态

如果您使用上下文菜单，代码可能类似:

def contextMenuEvent(self, event):
    menu = QMenu(self)
    delete_action = menu.addAction("删除元素")
    # ... 其他菜单项 ...
    
    action = menu.exec_(event.globalPos())
    if action == delete_action:
        self.delete_element()  # 使用上面修改过的方法

注意事项:

1. 确保在树状态发生变化的所有操作中都应用相同的保存和恢复逻辑
2. 如果删除操作会触发树的完全重建，可能需要在主窗口类的update_tree_widget方法中处理
3. 对于需要确认的删除操作，在用户确认后再保存和恢复状态
""" 