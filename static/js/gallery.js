// Getting the root element and appending an unordered list
const root = document.getElementById('root')
const ul = document.createElement('ul')
root.appendChild(ul)

// Root url
const base_url = 'http://127.0.0.1/api/media'

// Returns an object cointaining user and data from the current url, else returns null values
const getUrlParams = () => {
  const currentUrl = new URL(window.location.href)
  const user = currentUrl.searchParams.get('user')
  const date = currentUrl.searchParams.get('date')
  return {'user': user, 'date': date}
}

const handleImages = (apiUrl) => {
  urlParams = getUrlParams() // Gets the current url params
  if (urlParams.date != null) { // If there's a date in the current url set it in the request url string
    urlToFetch = apiUrl + '?user=' + urlParams.user + '&date=' + urlParams.date
  } else if (urlParams.user != null) { // Elif set only the user
    urlToFetch = apiUrl + '?user=' + urlParams.user
  } else { // Else set only the base url
    urlToFetch = apiUrl
  }
  fetch(urlToFetch) 
  .then(res => {
    res.json().then(dataJson => { // JSONize the response of the request
      if ('folders' in dataJson) { // If the returned dict is a folder type
        dataJson.folders.forEach(elem => { // For each element set the url to retrieve the content of the folder
          let newLink = null
          if (urlParams.user) // If the user is already in the current url, add date
            newLink = window.location.href + '&date=' + elem.name
          else { // ELse if there's nothing in the link, set the user
            newLink = window.location.href + '?user=' + elem.name
          }

          // Creating HTML elements
          const li = document.createElement('li')
          const a = document.createElement('a')
          a.href = newLink
          const div = document.createElement('div')
          div.className += 'gallery-folders'
          div.innerHTML = elem.name
          a.appendChild(div)
          li.appendChild(a)
          ul.appendChild(li)
        })
      } else if ('media' in dataJson) { // If the returned dict contains media
        dataJson.media.forEach(elem => { // For each media create the HTML element
          const li = document.createElement('li')
          const media = document.createElement(elem.content_tag)
          media.tagName === "VIDEO" ? media.setAttribute("controls", "controls") : ''
          const mediaString = "data:" + elem.media_type + ";" + "base64," + elem.data
          media.setAttribute('src', mediaString)
          media.className += "rendered-stories"
          li.appendChild(media)
          ul.appendChild(li)
        })
      }
    }
    )
  })
}

//Start the function
handleImages(base_url)
