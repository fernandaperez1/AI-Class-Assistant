import { auth } from "../firebase";
import { signOut } from "firebase/auth";
import { API_URL } from "../config";

/**
 * Creates or retrieves a user in the backend after Firebase authentication
 */
export async function syncUserWithBackend(firebaseUser) {
  try {
    // Check if user exists
    const getRes = await fetch(`${API_URL}/api/users/${firebaseUser.uid}`);
    
    if (getRes.ok) {
      const user = await getRes.json();
      console.log("User synced from backend:", user);
      return user;
    }
    
    if (getRes.status === 404) {
      // Create new user
      const createRes = await fetch(`${API_URL}/api/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firebase_uid: firebaseUser.uid,
          email: firebaseUser.email,
        }),
      });
      
      if (!createRes.ok) {
        throw new Error("Failed to create user in backend");
      }
      
      const newUser = await createRes.json();
      console.log("New user created in backend:", newUser);
      return newUser;
    }
    
    throw new Error("Failed to sync user with backend");
  } catch (error) {
    console.error("Error syncing user with backend:", error);
    throw error;
  }
}

/**
 * Logs out the user from Firebase
 */
export async function logout() {
  try {
    await signOut(auth);
    console.log("User logged out successfully");
  } catch (error) {
    console.error("Error logging out:", error);
    throw error;
  }
}

/**
 * Get the current Firebase user's ID token
 */
export async function getAuthToken() {
  const user = auth.currentUser;
  if (user) {
    return await user.getIdToken();
  }
  return null;
}

/**
 * Create authenticated fetch request with Firebase token
 */
export async function authenticatedFetch(url, options = {}) {
  const token = await getAuthToken();
  
  const headers = {
    ...options.headers,
    "Content-Type": "application/json",
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  return fetch(url, {
    ...options,
    headers,
  });
}
