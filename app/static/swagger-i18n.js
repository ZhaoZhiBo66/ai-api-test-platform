(() => {
  const translations = new Map([
    ["Authorize", "授权设置"], ["Try it out", "开始调试"], ["Execute", "发送请求"], ["Clear", "清除"], ["Cancel", "取消"],
    ["Parameters", "请求参数"], ["Request body", "请求体"], ["Responses", "响应结果"], ["Response body", "响应内容"],
    ["Response headers", "响应头"], ["Server response", "服务响应"], ["Example Value", "示例值"], ["Schema", "数据结构"],
    ["Description", "说明"], ["No parameters", "暂无参数"], ["Required", "必填"], ["Optional", "选填"], ["Available authorizations", "认证配置"],
    ["Authentication required", "需要认证"], ["Code", "状态码"], ["Details", "详情"]
  ]);
  const translate = () => document.querySelectorAll("button, h4, label, .opblock-section-header, .responses-inner h4").forEach((element) => {
    Array.from(element.childNodes).forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const original = node.nodeValue.trim();
        if (translations.has(original)) node.nodeValue = node.nodeValue.replace(original, translations.get(original));
      }
    });
  });
  new MutationObserver(translate).observe(document.documentElement, { childList:true, subtree:true });
  translate();
})();
