import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { VocabularyProvider } from "./api/VocabularyContext";
import { LandingPage } from "./routes/LandingPage";
import { SearchPage } from "./routes/SearchPage";
import { SchoolPage } from "./routes/SchoolPage";
import { NotFoundPage } from "./routes/NotFoundPage";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <App />,
      children: [
        { index: true, element: <LandingPage /> },
        { path: "search", element: <SearchPage /> },
        { path: "schools/:key", element: <SchoolPage /> },
        { path: "*", element: <NotFoundPage /> }
      ]
    }
  ],
  { future: { v7_relativeSplatPath: true } }
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <VocabularyProvider>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </VocabularyProvider>
  </StrictMode>
);