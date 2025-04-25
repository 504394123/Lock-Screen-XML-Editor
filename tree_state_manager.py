from lxml import etree

class TreeStateManager:
    """
    管理树视图状态的类，用于保存和恢复树视图的展开状态和滚动位置
    """
    def __init__(self, tree_widget):
        """
        初始化状态管理器
        
        Args:
            tree_widget: 要管理状态的树视图控件
        """
        self.tree_widget = tree_widget
        self.expanded_paths = []
        self.scroll_position = 0
        self.selected_paths = []
    
    def save_state(self):
        """
        保存当前树视图的状态，包括展开的节点和滚动位置
        """
        # 保存滚动位置
        scrollbar = self.tree_widget.verticalScrollBar()
        if scrollbar:
            self.scroll_position = scrollbar.value()
        
        # 保存展开状态
        self.expanded_paths = []
        self._save_expanded_state(None)
        
        # 保存选中状态
        self.selected_paths = []
        self._save_selected_state()
        
        return self
    
    def _get_item_path(self, item):
        """获取树节点的路径。"""
        path_parts = []
        current_item = item

        while current_item:
            if hasattr(current_item, 'element'):
                element = current_item.element
                if isinstance(element, etree._Comment):
                    # 对于注释节点，使用完整的注释文本作为路径部分
                    path_parts.insert(0, f"<!--{element.text.strip()}-->")
                else:
                    # 对于普通元素节点，使用标签名和索引
                    tag = element.tag
                    parent = current_item.parent()
                    if parent:
                        index = 0
                        for i in range(parent.childCount()):
                            sibling = parent.child(i)
                            if (hasattr(sibling, 'element') and 
                                sibling.element.tag == tag):
                                if sibling == current_item:
                                    break
                                index += 1
                        path_parts.insert(0, f"{tag}[{index}]")
                    else:
                        path_parts.insert(0, tag)
            current_item = current_item.parent()

        return '/'.join(path_parts)
    
    def _save_expanded_state(self, parent_item):
        """
        递归保存展开状态
        
        Args:
            parent_item: 父节点，如果为None则表示根节点
        """
        items = []
        if parent_item is None:
            # 获取顶层项目
            for i in range(self.tree_widget.topLevelItemCount()):
                items.append(self.tree_widget.topLevelItem(i))
        else:
            # 获取子项目
            for i in range(parent_item.childCount()):
                items.append(parent_item.child(i))
        
        # 遍历所有项目
        for item in items:
            if item.isExpanded():
                # 保存展开状态
                path = self._get_item_path(item)
                self.expanded_paths.append(path)
            
            # 递归处理子项目
            self._save_expanded_state(item)
    
    def _save_selected_state(self):
        """保存选中项的状态"""
        for item in self.tree_widget.selectedItems():
            path = self._get_item_path(item)
            self.selected_paths.append(path)
    
    def restore_state(self):
        """
        恢复树视图的状态
        """
        # 不再先收起所有节点，直接恢复展开状态
        # 遍历树中所有项目并根据保存的展开路径设置状态
        self._restore_expanded_state(None)
        
        # 恢复选中状态
        self.tree_widget.clearSelection()
        for path in self.selected_paths:
            item = self._find_item_by_path(path)
            if item:
                item.setSelected(True)
        
        # 最后恢复滚动位置
        scrollbar = self.tree_widget.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(self.scroll_position)
            
        # 强制刷新视图
        self.tree_widget.viewport().update()
    
    def _restore_expanded_state(self, parent_item):
        """
        递归恢复展开状态，而不是先收起所有节点
        
        Args:
            parent_item: 父节点，如果为None则表示根节点
        """
        items = []
        if parent_item is None:
            # 获取顶层项目
            for i in range(self.tree_widget.topLevelItemCount()):
                items.append(self.tree_widget.topLevelItem(i))
        else:
            # 获取子项目
            for i in range(parent_item.childCount()):
                items.append(parent_item.child(i))
        
        # 遍历所有项目
        for item in items:
            path = self._get_item_path(item)
            should_expand = path in self.expanded_paths
            
            # 如果该项在保存的展开路径中，则展开它
            if should_expand:
                item.setExpanded(True)
            else:
                item.setExpanded(False)
            
            # 递归处理子项目
            self._restore_expanded_state(item)
    
    def _collapse_all(self, parent_item):
        """
        递归收起所有节点
        
        Args:
            parent_item: 父节点，如果为None则表示根节点
        """
        items = []
        if parent_item is None:
            # 获取顶层项目
            for i in range(self.tree_widget.topLevelItemCount()):
                items.append(self.tree_widget.topLevelItem(i))
        else:
            # 获取子项目
            for i in range(parent_item.childCount()):
                items.append(parent_item.child(i))
        
        # 遍历所有项目
        for item in items:
            # 递归处理子项目
            self._collapse_all(item)
            
            # 收起节点
            item.setExpanded(False)
    
    def _find_item_by_path(self, path):
        """
        根据路径查找树节点
        
        Args:
            path: 节点路径元组
            
        Returns:
            找到的树节点，如果未找到则返回None
        """
        if not path:
            return None
        
        # 从根节点开始查找
        current_items = []
        for i in range(self.tree_widget.topLevelItemCount()):
            current_items.append(self.tree_widget.topLevelItem(i))
        
        # 逐级查找
        for level, path_text in enumerate(path):
            found = False
            
            # 检查当前级别的所有项目
            for item in current_items:
                item_text = item.text(0)
                
                # 如果有元素属性，使用更详细的比较
                if hasattr(item, 'element'):
                    element = item.element
                    if isinstance(element, etree._Comment):
                        # 对于注释节点，需要特殊处理
                        current_comment = element.text.strip()
                        path_comment = path_text
                        # 如果路径文本以注释标记开始，去除它们
                        if path_text.startswith('<!--') and path_text.endswith('-->'):
                            path_comment = path_text[4:-3].strip()
                        # 直接比较注释内容
                        if current_comment != path_comment:
                            continue
                    else:
                        # 处理普通元素
                        tag_part = path_text.split('[')[0].split('#')[0]
                        
                        # 检查标签是否匹配
                        if element.tag != tag_part:
                            continue
                        
                        # 如果有唯一ID，优先使用ID匹配
                        if '#' in path_text and hasattr(element, 'unique_id'):
                            id_part = path_text.split('#')[1]
                            if element.unique_id != id_part:
                                continue
                        
                        # 检查属性是否匹配
                        if '[' in path_text:
                            attrs_part = path_text.split('[')[1].strip(']').split(',')
                            match = True
                            for attr in attrs_part:
                                if '=' in attr:
                                    key, value = attr.split('=')
                                    if element.get(key) != value:
                                        match = False
                                        break
                            if not match:
                                continue
                
                # 如果是普通文本比较
                elif item_text != path_text:
                    continue
                
                # 找到匹配项
                if level == len(path) - 1:
                    # 如果是最后一级，返回该项
                    return item
                else:
                    # 如果不是最后一级，继续查找下一级
                    current_items = []
                    for i in range(item.childCount()):
                        current_items.append(item.child(i))
                    found = True
                    break
            
            if not found:
                # 如果当前级别未找到匹配项，则返回None
                return None
        
        return None 