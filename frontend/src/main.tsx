// Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
// SPDX-License-Identifier: MIT
/**
 * Application entry point.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
