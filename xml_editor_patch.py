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


"""
修改说明:

1. 将上述代码替换XMLEditorWindow类中现有的delete_elements方法
2. 确保在文件顶部导入了必要的模块:
   from tree_state_manager import TreeStateManager
   from PyQt5.QtCore import QTimer
3. 将save_expand_state参数设为False，因为我们现在使用自己的状态管理器
4. 添加延迟恢复机制，确保UI完全更新后再恢复状态

如何应用这个补丁:

1. 打开xml_editor.py文件
2. 在文件顶部添加导入语句:
   from tree_state_manager import TreeStateManager
   from PyQt5.QtCore import QTimer
3. 找到delete_elements方法并替换为上述代码
4. 保存文件

这个修改也适用于其他修改树结构的方法，如cut_elements等。
对于每个会变更树结构的方法，都可以应用相同的模式:
- 保存状态
- 执行操作
- 更新UI
- 延迟恢复状态
""" 