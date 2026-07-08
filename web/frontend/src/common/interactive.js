import { ElMessage, ElMessageBox, ElLoading } from 'element-plus';


// 创建一个简单的loading元素
let loadingInstance = null;

export function networkError(res = '') {
    ElMessage.error({ message: '网络超时', duration: 3000 });
    console.log("@@@networkError-->" + res);
}

export function showToast(title,
                          icon = 'success',
                          duration = 2000
) {
    ElMessage({ message: title, type: icon, duration });
}

export function showModal(title,
                          content,
                          confirmCallback = () => {},
                          cancelCallback = () => {},
                          confirmText = '确定',
                          cancelText = '取消',
                          showCancel = true,
) {
    ElMessageBox.confirm(content, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        showCancelButton: showCancel,
        type: 'warning',
        closeOnClickModal: false,
    }).then(() => {
        confirmCallback();
    }).catch(() => {
        cancelCallback();
    });
}

export function showLoading(title = '加载中', mask = true) {
    if (loadingInstance) {
        if (typeof loadingInstance.close === 'function') { loadingInstance.close(); }
        loadingInstance = null;
    }
    loadingInstance = ElLoading.service({
        text: title,
        lock: !!mask,
        background: mask ? 'rgba(0, 0, 0, 0.5)' : 'rgba(0,0,0,0)'
    });
    return loadingInstance;
}

export function hideLoading() {
    if (loadingInstance) {
        if (typeof loadingInstance.close === 'function') { loadingInstance.close(); }
        loadingInstance = null;
    }
}

export function showActionSheet(itemList,
                                success = () => {},
                                fail = () => {},
                                itemColor = '#111827'
) {
    // 创建一个简单的操作表
    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.bottom = '0';
    container.style.left = '0';
    container.style.width = '100%';
    container.style.backgroundColor = 'white';
    container.style.borderTopLeftRadius = '12px';
    container.style.borderTopRightRadius = '12px';
    container.style.zIndex = '9999';
    container.style.boxShadow = '0 -2px 10px rgba(0, 0, 0, 0.1)';
    
    // 创建遮罩层
    const mask = document.createElement('div');
    mask.style.position = 'fixed';
    mask.style.top = '0';
    mask.style.left = '0';
    mask.style.width = '100%';
    mask.style.height = '100%';
    mask.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
    mask.style.zIndex = '9998';
    
    // 点击遮罩层关闭
    mask.addEventListener('click', () => {
        document.body.removeChild(container);
        document.body.removeChild(mask);
        fail({ errMsg: 'showActionSheet:fail cancel' });
    });
    
    // 添加选项
    itemList.forEach((item, index) => {
        const button = document.createElement('div');
        button.textContent = item;
        button.style.padding = '15px';
        button.style.textAlign = 'center';
        button.style.borderBottom = '1px solid #eee';
        button.style.color = itemColor;
        button.style.cursor = 'pointer';
        
        button.addEventListener('click', () => {
            document.body.removeChild(container);
            document.body.removeChild(mask);
            success(index);
        });
        
        container.appendChild(button);
    });
    
    // 添加取消按钮
    const cancelButton = document.createElement('div');
    cancelButton.textContent = '取消';
    cancelButton.style.padding = '15px';
    cancelButton.style.textAlign = 'center';
    cancelButton.style.color = '#333';
    cancelButton.style.cursor = 'pointer';
    cancelButton.style.marginTop = '8px';
    cancelButton.style.fontWeight = 'bold';
    
    cancelButton.addEventListener('click', () => {
        document.body.removeChild(container);
        document.body.removeChild(mask);
        fail({ errMsg: 'showActionSheet:fail cancel' });
    });
    
    container.appendChild(cancelButton);
    
    document.body.appendChild(mask);
    document.body.appendChild(container);
}