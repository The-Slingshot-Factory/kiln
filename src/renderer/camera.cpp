#include "camera.h"

#include <algorithm>
#include <cmath>

Camera::Camera() = default;

void Camera::reset()
{
    distance = 10.0f;
    yaw = 45.0f;
    pitch = 30.0f;
    target = glm::vec3(0.0f);
}

glm::vec3 Camera::getPosition() const
{
    float pitchRad = glm::radians(pitch);
    float yawRad = glm::radians(yaw);
    
    float x = distance * cos(pitchRad) * sin(yawRad);
    float y = distance * sin(pitchRad);
    float z = distance * cos(pitchRad) * cos(yawRad);
    
    return target + glm::vec3(x, y, z);
}

glm::vec3 Camera::getRight() const
{
    float yawRad = glm::radians(yaw);
    return glm::vec3(cos(yawRad), 0.0f, -sin(yawRad));
}

glm::mat4 Camera::getViewMatrix() const
{
    return glm::lookAt(getPosition(), target, glm::vec3(0.0f, 1.0f, 0.0f));
}

glm::mat4 Camera::getProjectionMatrix(float aspectRatio) const
{
    return glm::perspective(glm::radians(fov), aspectRatio, nearPlane, farPlane);
}

void Camera::orbit(float deltaX, float deltaY)
{
    yaw -= deltaX * ORBIT_SENSITIVITY;
    pitch += deltaY * ORBIT_SENSITIVITY;
    pitch = std::clamp(pitch, -89.0f, 89.0f);
}

void Camera::pan(float deltaX, float deltaY)
{
    glm::vec3 right = getRight();
    target -= right * deltaX * PAN_SENSITIVITY * distance;
    target.y += deltaY * PAN_SENSITIVITY * distance;
}

void Camera::zoom(float delta)
{
    distance -= delta * ZOOM_SENSITIVITY;
    distance = std::clamp(distance, 1.0f, 100.0f);
}

void Camera::moveForward(float speed)
{
    glm::vec3 forward = -glm::normalize(getPosition() - target);
    forward.y = 0.0f;  // Keep movement on horizontal plane
    forward = glm::normalize(forward);
    target += forward * speed * distance * 0.03f;
}

void Camera::moveBackward(float speed)
{
    glm::vec3 forward = -glm::normalize(getPosition() - target);
    forward.y = 0.0f;  // Keep movement on horizontal plane
    forward = glm::normalize(forward);
    target -= forward * speed * distance * 0.03f;
}

void Camera::moveLeft(float speed)
{
    glm::vec3 right = getRight();
    target -= right * speed * distance * 0.03f;
}

void Camera::moveRight(float speed)
{
    glm::vec3 right = getRight();
    target += right * speed * distance * 0.03f;
}


