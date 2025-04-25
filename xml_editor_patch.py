"""
修复xml_editor.py中delete_elements方法的补丁，使用TreeStateManager保持元素组的展开状态

这个补丁提供了如何修改XMLEditorWindow类中的delete_elements方法，
以确保在删除元素后，树视图的展开状态得到正确保存和恢复。
"""

from tree_state_manager import TreeStateManager
from PyQt5.QtCore import QTimer

# 需要对以下方法进行修改：

def delete_elements(self):
    """
    删除所选元素的方法，添加了状态保存和恢复
    """
    selected_items = self.tree_widget.selectedItems()
    if not selected_items:
        return
    
    # 创建状态管理器并保存当前状态
    tree_state = TreeStateManager(self.tree_widget).save_state()
    
    # 执行删除操作
    for item in selected_items:
        element = item.element
        parent = element.getparent()
        
        if parent is not None:
            parent.remove(element)
    
    # 更新UI
    self.update_tree_widget(save_expand_state=False)  # 不使用旧的保存状态方法
    self.update_code_view()
    
    # 使用延迟调用恢复状态，确保UI已完全更新
    QTimer.singleShot(100, lambda: tree_state.restore_state())

