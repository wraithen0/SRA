import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider
      router={createBrowserRouter([
        {
          path: "/",
          element: <App />,
          children: [{ index: true, element: <div>Search</div> }]
        }
      ])}
    />
  </StrictMode>
);
