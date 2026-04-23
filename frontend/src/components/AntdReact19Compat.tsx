'use client';

import { unstableSetRender } from 'antd';
import { createRoot, type Root } from 'react-dom/client';

declare global {
  interface HTMLElement {
    __antd_react_root__?: Root;
  }
}

let isPatched = false;

if (!isPatched) {
  unstableSetRender((node, container) => {
    container.__antd_react_root__ ||= createRoot(container);
    const root = container.__antd_react_root__;

    root.render(node);

    return async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      root.unmount();
    };
  });

  isPatched = true;
}

export default function AntdReact19Compat() {
  return null;
}
