import { API_URL } from "../config";

export const getPresentationInfo = async (classId) => {
  const response = await fetch(
    `${API_URL}/api/classes/${classId}/presentation-info`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch presentation info");
  }
  return response.json();
};

export const convertPresentationToPDF = async (presentationId) => {
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/convert`,
    {
      method: "POST",
    }
  );
  if (!response.ok) {
    throw new Error("Failed to convert presentation");
  }
  return response.json();
};

export const convertPresentationToImages = async (presentationId) => {
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/convert-to-images`,
    {
      method: "POST",
    }
  );
  if (!response.ok) {
    throw new Error("Failed to convert presentation to images");
  }
  return response.json();
};

export const getSlideImageUrl = (presentationId, slideNumber) => {
  return `${API_URL}/api/presentations/${presentationId}/slides/${slideNumber}`;
};

export const getPresentationText = async (presentationId) => {
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/text`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch presentation text");
  }
  return response.json();
};

export const startPresentation = async (presentationId, telegramChatId = null, currentSlide = 1) => {
  const body = {
    current_slide: currentSlide
  };
  
  //only include telegram_chat_id if it's provided and not null, this way the pptx can be seen without linking
  if (telegramChatId !== null && telegramChatId !== undefined) {
    body.telegram_chat_id = telegramChatId;
  }
  
  console.log(`Starting presentation ${presentationId} with body:`, body);
  
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/start`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || "Failed to start presentation");
  }
  return response.json();
};

export const endPresentation = async (presentationId, telegramChatId = null) => {
  const body = {};
  
  //only include telegram_chat_id if it's provided and not null
  if (telegramChatId !== null && telegramChatId !== undefined) {
    body.telegram_chat_id = telegramChatId;
  }
  
  console.log(`Ending presentation ${presentationId} with body:`, body);
  
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/end`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || "Failed to end presentation");
  }
  return response.json();
};

export const getPresentationQuestions = async (presentationId) => {
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/questions`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch questions");
  }
  return response.json();
};

export const addQuestion = async (presentationId, questionData) => {
  const response = await fetch(
    `${API_URL}/api/presentations/${presentationId}/questions`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(questionData),
    }
  );
  if (!response.ok) {
    throw new Error("Failed to add question");
  }
  return response.json();
};
