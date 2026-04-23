'use client';

import { unstableSetRender } from 'antd';
import { createRoot, type Root } from 'react-dom/client';

type AntdContainer = Element | DocumentFragment;

type AntdContainerWithRoot = AntdContainer & {
  __antd_react_root__?: Root;
};

let isPatched = false;

if (!isPatched) {
  unstableSetRender((node, container) => {
    const patchedContainer = container as AntdContainerWithRoot;

    patchedContainer.__antd_react_root__ ||= createRoot(container);
    const root = patchedContainer.__antd_react_root__;

    root.render(node);

    return async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      root.unmount();
      delete patchedContainer.__antd_react_root__;
    };
  });

  isPatched = true;
}

export default function AntdReact19Compat() {
  return null;
}